from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from .codex_runner import CodexRunner
from .config import ProjectConfig, Settings
from .discord_output import chunk_output, extract_assistant_response, summarize_result
from .locks import JobRegistry
from .logging_store import LoggingStore
from .prompt import ChannelMessage, build_prompt


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
        self._bind_events()

    async def start(self, token: str) -> None:
        await self._client.start(token)

    def _bind_events(self) -> None:
        client = self._client

        @client.event
        async def on_ready():
            print(f"DiscordCodex connected as {client.user}")

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
        elif command == "!help":
            await message.channel.send("Commands: `!status`, `!cancel`, `!tail`, `!projects`, `!help`.")

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
        await message.channel.send(f"Codex is working on `{project.name}`...")
        recent = await self._recent_messages(message, project.include_recent_messages)
        prompt = build_prompt(project, message.channel.name, recent, content)
        paths.prompt.write_text(prompt, encoding="utf-8")
        result = await self.runner.run(project=project, prompt=prompt)
        paths.log.write_text(result.output, encoding="utf-8")

        response = extract_assistant_response(result.output) if result.exit_code == 0 else None
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
            },
        )
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
