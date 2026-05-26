from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

from .codex_runner import CodexProgress, CodexRunner
from .config import ProjectConfig, Settings, load_settings
from .discord_output import chunk_output, extract_assistant_response, help_message, summarize_result
from .guide_store import GuideStore
from .github_provisioning import GitHubProvisioner
from .locks import JobRegistry
from .logging_store import LoggingStore
from .prompt import ChannelMessage, build_prompt
from .session_store import ChannelSession, SessionStore


def _status_from_progress(progress: CodexProgress) -> str:
    message = progress.message.strip()
    if message.startswith("Codex is "):
        message = message[len("Codex is ") :]
    elif message.startswith("Codex "):
        message = message[len("Codex ") :]
    if message:
        return message[:1].lower() + message[1:]
    return progress.kind


async def run_bot(settings: Settings) -> None:
    try:
        import discord
    except ImportError as exc:
        raise RuntimeError("discord.py is required. Install with: pip install -e .") from exc

    intents = discord.Intents.default()
    intents.message_content = True
    client = DiscordCodexClient(settings=settings, intents=intents)
    await client.start(settings.discord_token)


class DiscordCodexClient:
    def __init__(self, settings: Settings, intents):
        try:
            import discord
        except ImportError as exc:
            raise RuntimeError("discord.py is required. Install with: pip install -e .") from exc

        class _Client(discord.Client):
            pass

        self._client = _Client(intents=intents)
        self.settings = settings
        self.jobs = JobRegistry(settings.max_concurrent_jobs_global)
        self.runner = CodexRunner(settings.codex_bin, settings.cancel_grace_seconds)
        self.logs = LoggingStore(settings.data_dir)
        self.sessions = SessionStore(settings.data_dir)
        self.guides = GuideStore(settings.data_dir)
        self.github_poll_lock = asyncio.Lock()
        self.github_poll_task = None
        self._bind_events()

    async def start(self, token: str) -> None:
        await self._client.start(token)

    def _bind_events(self) -> None:
        client = self._client

        @client.event
        async def on_ready():
            print(f"DiscordCodex connected as {client.user}")
            self._start_github_polling()

        @client.event
        async def on_message(message):
            await self.handle_message(message)

    async def handle_message(self, message) -> None:
        if message.author.bot:
            return
        if message.guild is None:
            return
        if str(message.guild.id) != self.settings.allowed_guild_id:
            return
        if str(message.author.id) not in self.settings.allowed_user_ids:
            return

        content = (message.content or "").strip()
        if content.startswith("!"):
            await self._handle_command(message, content)
            return

        project = self.settings.channels.get(str(message.channel.id))
        if not project:
            return
        if not content:
            if getattr(message, "attachments", None):
                await message.channel.send("Attachments are not supported in v1.")
            return
        if getattr(message, "attachments", None):
            await message.channel.send("Attachments are not supported in v1; using text only.")
        if self._guides().mark_sent_if_first(str(message.channel.id)):
            await message.channel.send(help_message())
        if self.jobs.get(str(message.channel.id)):
            await message.channel.send("Codex is already running for this channel. Use `!status` or `!cancel`.")
            return

        async with self.jobs.reserve(str(message.channel.id), project.name):
            task = asyncio.create_task(self._run_codex_for_message(message, project, content))
            await self.jobs.set_task(str(message.channel.id), task)
            await task

    async def _handle_command(self, message, content: str) -> None:
        command = content.split()[0].lower()
        channel_id = str(message.channel.id)
        if command == "!status":
            job = self.jobs.get(channel_id)
            if job:
                if job.latest_status:
                    await message.channel.send(f"Codex is running for `{job.project_name}`: {job.latest_status}")
                else:
                    await message.channel.send(f"Codex is running for `{job.project_name}`.")
            else:
                await message.channel.send("No Codex job is running for this channel.")
        elif command == "!cancel":
            if await self.jobs.cancel(channel_id):
                await message.channel.send("Cancellation requested.")
            else:
                await message.channel.send("No Codex job is running for this channel.")
        elif command == "!projects":
            names = ", ".join(sorted(project.name for project in self.settings.channels.values()))
            await message.channel.send(f"Configured projects: {names}")
        elif command == "!tail":
            await self._send_tail(message)
        elif command == "!session":
            await self._send_session(message)
        elif command == "!new":
            await self._clear_session(message)
        elif command == "!help":
            await message.channel.send(help_message())
        elif command == "!pollgh":
            await self._handle_pollgh(message)

    async def _send_session(self, message) -> None:
        project = self.settings.channels.get(str(message.channel.id))
        if not project:
            await message.channel.send("This channel is not configured for a project.")
            return
        session = self.sessions.load(str(message.channel.id))
        if not session:
            await message.channel.send(f"No Codex session is stored for `{project.name}` yet.")
            return
        await message.channel.send(
            f"Codex session for `{project.name}`: `{session.thread_id[:8]}`. Use `!new` to start fresh."
        )

    async def _clear_session(self, message) -> None:
        project = self.settings.channels.get(str(message.channel.id))
        if not project:
            await message.channel.send("This channel is not configured for a project.")
            return
        self.sessions.clear(str(message.channel.id))
        await message.channel.send(f"Started a fresh Codex session for `{project.name}`. Send a message to begin.")

    def _guides(self) -> GuideStore:
        if not hasattr(self, "guides"):
            self.guides = GuideStore(self.settings.data_dir)
        return self.guides

    def _start_github_polling(self) -> None:
        config = self.settings.github_provisioning
        if not config or not config.enabled:
            return
        if self.github_poll_task and not self.github_poll_task.done():
            return
        self.github_poll_task = asyncio.create_task(self._github_poll_loop())

    async def _github_poll_loop(self) -> None:
        config = self.settings.github_provisioning
        if not config:
            return
        if config.run_on_startup:
            await self._run_github_poll(trigger="startup")
        while True:
            await asyncio.sleep(config.poll_interval_seconds)
            await self._run_github_poll(trigger="scheduled")

    async def _handle_pollgh(self, message) -> None:
        config = self.settings.github_provisioning
        if not config or not config.enabled:
            await message.channel.send("GitHub provisioning is not enabled.")
            return
        if self._github_lock().locked():
            await message.channel.send("GitHub poll is already running.")
            return
        await message.channel.send("GitHub poll started. Results will be posted in #neo.")
        report = await self._run_github_poll(trigger="manual")
        if report is not None:
            await message.channel.send("GitHub poll finished. Results posted in #neo.")

    async def _run_github_poll(self, *, trigger: str):
        config = self.settings.github_provisioning
        if not config or not config.enabled:
            return None
        lock = self._github_lock()
        if lock.locked():
            return None
        async with lock:
            guild = self._client.get_guild(int(self.settings.allowed_guild_id))
            if guild is None:
                return None
            provisioner = GitHubProvisioner(
                config=config,
                config_path=self.settings.config_path,
                discord_client=self._client,
            )
            report = await provisioner.run_for_guild(
                guild,
                {project.name for project in self.settings.channels.values()},
            )
            self._reload_settings()
            return report

    def _github_lock(self) -> asyncio.Lock:
        if not hasattr(self, "github_poll_lock"):
            self.github_poll_lock = asyncio.Lock()
        return self.github_poll_lock

    def _reload_settings(self) -> None:
        self.settings = load_settings(config_path=str(self.settings.config_path))

    async def _send_tail(self, message) -> None:
        project = self.settings.channels.get(str(message.channel.id))
        if not project:
            await message.channel.send("This channel is not configured for a project.")
            return
        log_dir = self.settings.data_dir / "logs" / project.safe_name
        logs = sorted(log_dir.glob("*.log")) if log_dir.exists() else []
        if not logs:
            await message.channel.send("No log exists for this channel yet.")
            return
        tail = logs[-1].read_text(encoding="utf-8", errors="replace")[-project.max_output_chars_per_message :]
        await message.channel.send(tail or "(latest log is empty)")

    async def _run_codex_for_message(self, message, project: ProjectConfig, content: str) -> None:
        paths = self.logs.create_run_paths(project.name)
        started = datetime.now(timezone.utc)
        progress_message = await message.channel.send("Codex is starting...")
        progress_text = "Codex is starting..."
        last_edit_at = 0.0

        async def update_progress(progress: CodexProgress, *, force: bool = False) -> None:
            nonlocal progress_text, last_edit_at
            await self.jobs.set_latest_status(str(message.channel.id), _status_from_progress(progress))
            if progress.message == progress_text:
                return
            now = time.monotonic()
            if not force and last_edit_at and now - last_edit_at < 2.0:
                return
            try:
                await progress_message.edit(content=progress.message)
            except Exception:
                return
            progress_text = progress.message
            last_edit_at = now

        stored_session = self.sessions.load(str(message.channel.id)) if project.persistent_session else None
        recent = [] if stored_session else await self._recent_messages(message, project.include_recent_messages)
        prompt = build_prompt(
            project,
            message.channel.name,
            recent,
            content,
            resumed_session=stored_session is not None,
        )
        paths.prompt.write_text(prompt, encoding="utf-8")
        result = await self.runner.run(
            project=project,
            prompt=prompt,
            session_id=stored_session.thread_id if stored_session else None,
            progress_callback=update_progress,
        )
        if result.exit_code == 0 and not result.cancelled and not result.timed_out:
            await update_progress(CodexProgress(message="Codex finished.", kind="finish"), force=True)
        else:
            await update_progress(CodexProgress(message="Codex stopped.", kind="finish"), force=True)
        paths.log.write_text(result.output, encoding="utf-8")

        response = result.assistant_response or (
            extract_assistant_response(result.output) if result.exit_code == 0 else None
        )
        if response:
            chunks, truncated = chunk_output(
                response,
                max_chars=project.max_output_chars_per_message,
                max_chunks=self.settings.max_output_chunks,
            )
            for chunk in chunks:
                await message.channel.send(chunk)
            if truncated:
                await message.channel.send("Response truncated. Use `!tail` for details.")
        elif result.exit_code == 0:
            await message.channel.send("Codex finished, but I could not extract a clean response. Use `!tail` for details.")

        self.logs.write_metadata(
            paths,
            {
                "project": project.name,
                "channel_id": str(message.channel.id),
                "user_id": str(message.author.id),
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": result.duration_seconds,
                "cwd": str(project.cwd),
                "command": result.command,
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "cancelled": result.cancelled,
                "thread_id": result.thread_id or (stored_session.thread_id if stored_session else None),
                "resumed_session": stored_session is not None,
            },
        )
        if project.persistent_session and result.exit_code == 0 and not result.cancelled and not result.timed_out:
            thread_id = result.thread_id or (stored_session.thread_id if stored_session else None)
            if thread_id:
                now = datetime.now(timezone.utc).isoformat()
                self.sessions.save(
                    ChannelSession(
                        channel_id=str(message.channel.id),
                        project_safe_name=project.safe_name,
                        thread_id=thread_id,
                        created_at=stored_session.created_at if stored_session else started.isoformat(),
                        updated_at=now,
                        last_log_path=str(paths.log),
                    )
                )

        if stored_session and result.exit_code != 0 and not result.cancelled and not result.timed_out:
            await message.channel.send("Codex could not resume the stored session. Use `!new` to start fresh.")
        if result.exit_code != 0 or result.cancelled or result.timed_out:
            await message.channel.send(
                summarize_result(
                    project.name,
                    result.exit_code,
                    result.duration_seconds,
                    str(paths.log),
                    cancelled=result.cancelled,
                    timed_out=result.timed_out,
                )
            )

    async def _recent_messages(self, message, limit: int) -> list[ChannelMessage]:
        if limit <= 0:
            return []
        items = []
        async for recent in message.channel.history(limit=limit + 1, oldest_first=False):
            if recent.id == message.id:
                continue
            items.append(
                ChannelMessage(
                    author=getattr(recent.author, "display_name", str(recent.author)),
                    content=recent.content or "",
                    is_bot=recent.author.bot,
                )
            )
        items.reverse()
        return items
