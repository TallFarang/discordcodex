import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from discordcodex.bot import DiscordCodexClient
from discordcodex.codex_runner import CodexProgress, CodexResult
from discordcodex.config import GitHubProvisioningConfig, ProjectConfig, Settings
from discordcodex.discord_output import help_message
from discordcodex.locks import JobRegistry
from discordcodex.session_store import ChannelSession, SessionStore


TEST_CHANNEL_ID = "100000000000000001"
TEST_GUILD_ID = "100000000000000002"
TEST_USER_ID = "100000000000000003"


class FakeChannel:
    def __init__(self, channel_id=TEST_CHANNEL_ID):
        self.id = int(channel_id)
        self.name = "demo"
        self.sent = []
        self.messages = []

    async def send(self, content):
        self.sent.append(content)
        sent_message = FakeSentMessage(content)
        self.messages.append(sent_message)
        return sent_message


class FakeSentMessage:
    def __init__(self, content):
        self.content = content
        self.edits = []

    async def edit(self, content):
        self.content = content
        self.edits.append(content)


class FakeDiscordClient:
    def __init__(self):
        self.events = {}
        self.user = "discordcodex-test"
        self.channel = FakeChannel()
        self.guild = SimpleNamespace(id=int(TEST_GUILD_ID))

    def event(self, func):
        self.events[func.__name__] = func
        return func

    def get_channel(self, channel_id):
        if channel_id == self.channel.id:
            return self.channel
        return None

    def get_guild(self, guild_id):
        if guild_id == self.guild.id:
            return self.guild
        return None


class BotCommandTests(unittest.TestCase):
    def test_session_and_new_commands_report_and_clear_stored_session(self):
        asyncio.run(self._session_and_new_commands())

    async def _session_and_new_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "project"
            project_dir.mkdir()
            data_dir = root / "data"
            data_dir.mkdir()
            project = ProjectConfig(
                channel_id=TEST_CHANNEL_ID,
                name="demo",
                safe_name="demo",
                cwd=project_dir,
                codex_home=None,
                timeout_seconds=30,
                include_recent_messages=10,
                codex_args=["--full-auto"],
                max_output_chars_per_message=1800,
                persistent_session=True,
            )
            settings = Settings(
                discord_token="test-token",
                allowed_guild_id=TEST_GUILD_ID,
                allowed_user_ids={TEST_USER_ID},
                config_path=root / "projects.json",
                data_dir=data_dir,
                codex_bin="codex",
                channels={TEST_CHANNEL_ID: project},
                max_concurrent_jobs_global=1,
                max_output_chunks=4,
                cancel_grace_seconds=5,
                log_level="INFO",
            )
            store = SessionStore(data_dir)
            store.save(
                ChannelSession(
                    channel_id=TEST_CHANNEL_ID,
                    project_safe_name="demo",
                    thread_id="019d8056-e1a1-7b20-a367-c7459e072546",
                    created_at="2026-04-12T06:16:56+00:00",
                    updated_at="2026-04-12T06:17:12+00:00",
                    last_log_path="/data/logs/demo/run.log",
                )
            )

            client = DiscordCodexClient.__new__(DiscordCodexClient)
            client.settings = settings
            client.sessions = store
            channel = FakeChannel()
            message = SimpleNamespace(channel=channel)

            await client._handle_command(message, "!session")
            await client._handle_command(message, "!new")
            await client._handle_command(message, "!session")

            self.assertIn("019d8056", channel.sent[0])
            self.assertEqual(channel.sent[1], "Started a fresh Codex session for `demo`. Send a message to begin.")
            self.assertEqual(channel.sent[2], "No Codex session is stored for `demo` yet.")

    def test_ready_event_does_not_send_startup_guides(self):
        asyncio.run(self._ready_event_does_not_send_startup_guides())

    async def _ready_event_does_not_send_startup_guides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self._settings(root)
            client = DiscordCodexClient.__new__(DiscordCodexClient)
            client.settings = settings
            client._client = FakeDiscordClient()

            client._bind_events()
            await client._client.events["on_ready"]()

            self.assertEqual(client._client.channel.sent, [])

    def test_help_command_still_sends_usage_guide(self):
        asyncio.run(self._help_command_still_sends_usage_guide())

    async def _help_command_still_sends_usage_guide(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = DiscordCodexClient.__new__(DiscordCodexClient)
            client.settings = self._settings(root)
            channel = FakeChannel()
            message = SimpleNamespace(channel=channel)

            await client._handle_command(message, "!help")

            self.assertEqual(channel.sent, [help_message()])

    def test_first_normal_message_sends_guide_once_and_still_runs_codex(self):
        asyncio.run(self._first_normal_message_sends_guide_once_and_still_runs_codex())

    async def _first_normal_message_sends_guide_once_and_still_runs_codex(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self._settings(root)
            client = DiscordCodexClient.__new__(DiscordCodexClient)
            client.settings = settings
            client.jobs = JobRegistry(settings.max_concurrent_jobs_global)

            async def fake_run(message, project, content):
                await message.channel.send(f"ran {project.name}: {content}")

            client._run_codex_for_message = fake_run

            first_channel = FakeChannel()
            first = SimpleNamespace(
                author=SimpleNamespace(bot=False, id=int(TEST_USER_ID)),
                guild=SimpleNamespace(id=int(TEST_GUILD_ID)),
                channel=first_channel,
                content="do the first thing",
                attachments=[],
            )

            await client.handle_message(first)

            self.assertEqual(first_channel.sent[0], help_message())
            self.assertEqual(first_channel.sent[1], "ran demo: do the first thing")

            second_channel = FakeChannel()
            second = SimpleNamespace(
                author=SimpleNamespace(bot=False, id=int(TEST_USER_ID)),
                guild=SimpleNamespace(id=int(TEST_GUILD_ID)),
                channel=second_channel,
                content="do the next thing",
                attachments=[],
            )

            await client.handle_message(second)

            self.assertEqual(second_channel.sent, ["ran demo: do the next thing"])

    def test_run_codex_edits_single_progress_message_and_sends_response(self):
        asyncio.run(self._run_codex_edits_progress())

    async def _run_codex_edits_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self._settings(root)
            client = DiscordCodexClient.__new__(DiscordCodexClient)
            client.settings = settings
            client.jobs = JobRegistry(settings.max_concurrent_jobs_global)
            client.logs = SimpleNamespace(
                create_run_paths=lambda project_name: SimpleNamespace(
                    prompt=root / "prompt.txt",
                    log=root / "run.log",
                    metadata=root / "metadata.json",
                ),
                write_metadata=lambda paths, metadata: None,
            )
            client.sessions = SimpleNamespace(load=lambda channel_id: None)
            async def no_recent_messages(message, limit):
                return []

            client._recent_messages = no_recent_messages

            class FakeRunner:
                async def run(self, **kwargs):
                    callback = kwargs["progress_callback"]
                    await callback(CodexProgress(message="Codex is inspecting files...", kind="inspect"))
                    await callback(CodexProgress(message="Codex is inspecting files...", kind="inspect"))
                    await callback(CodexProgress(message="Codex is preparing a response...", kind="response"))
                    return CodexResult(
                        exit_code=0,
                        output='{"type": "item.completed", "item": {"type": "agent_message", "text": "hello"}}\n',
                        duration_seconds=1.0,
                        timed_out=False,
                        cancelled=False,
                        command=["codex", "<prompt redacted>"],
                        assistant_response="hello",
                    )

            client.runner = FakeRunner()
            channel = FakeChannel()
            message = SimpleNamespace(
                channel=channel,
                author=SimpleNamespace(id=int(TEST_USER_ID)),
            )

            await client._run_codex_for_message(message, settings.channels[TEST_CHANNEL_ID], "do work")

            self.assertEqual(channel.sent[0], "Codex is starting...")
            self.assertEqual(channel.sent[1], "hello")
            self.assertEqual(len(channel.messages), 2)
            self.assertIn("Codex is inspecting files...", channel.messages[0].edits)
            self.assertEqual(channel.messages[0].edits[-1], "Codex finished.")

    def test_status_reports_latest_progress_when_job_is_running(self):
        asyncio.run(self._status_reports_latest_progress())

    async def _status_reports_latest_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self._settings(root)
            client = DiscordCodexClient.__new__(DiscordCodexClient)
            client.settings = settings
            client.jobs = JobRegistry(settings.max_concurrent_jobs_global)
            channel = FakeChannel()
            message = SimpleNamespace(channel=channel)

            async with client.jobs.reserve(TEST_CHANNEL_ID, "demo"):
                await client.jobs.set_latest_status(TEST_CHANNEL_ID, "inspecting files...")
                await client._handle_command(message, "!status")

            self.assertEqual(channel.sent, ["Codex is running for `demo`: inspecting files..."])

    def test_pollgh_runs_github_provisioning(self):
        asyncio.run(self._pollgh_runs_github_provisioning())

    async def _pollgh_runs_github_provisioning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = self._settings(root)
            settings = Settings(
                discord_token=settings.discord_token,
                allowed_guild_id=settings.allowed_guild_id,
                allowed_user_ids=settings.allowed_user_ids,
                config_path=settings.config_path,
                data_dir=settings.data_dir,
                codex_bin=settings.codex_bin,
                channels=settings.channels,
                max_concurrent_jobs_global=settings.max_concurrent_jobs_global,
                max_output_chunks=settings.max_output_chunks,
                cancel_grace_seconds=settings.cancel_grace_seconds,
                log_level=settings.log_level,
                github_provisioning=GitHubProvisioningConfig(
                    enabled=True,
                    owner="TallFarang",
                    poll_interval_seconds=3600,
                    run_on_startup=True,
                    project_root=root / "projects",
                    codex_home_root=root / "codex-home",
                    codex_home_template=None,
                    admin_channel_name="neo",
                    discord_category_id=None,
                    include_archived=False,
                ),
            )
            client = DiscordCodexClient.__new__(DiscordCodexClient)
            client.settings = settings
            client._client = FakeDiscordClient()
            client._reload_settings = lambda: None
            channel = FakeChannel()
            message = SimpleNamespace(channel=channel)

            class FakeProvisioner:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

                async def run_for_guild(self, guild, existing_project_names):
                    return SimpleNamespace()

            with patch("discordcodex.bot.GitHubProvisioner", FakeProvisioner):
                await client._handle_command(message, "!pollgh")

            self.assertEqual(
                channel.sent,
                [
                    "GitHub poll started. Results will be posted in #neo.",
                    "GitHub poll finished. Results posted in #neo.",
                ],
            )

    def _settings(self, root: Path) -> Settings:
        project_dir = root / "project"
        project_dir.mkdir()
        data_dir = root / "data"
        data_dir.mkdir()
        project = ProjectConfig(
            channel_id=TEST_CHANNEL_ID,
            name="demo",
            safe_name="demo",
            cwd=project_dir,
            codex_home=None,
            timeout_seconds=30,
            include_recent_messages=10,
            codex_args=["--full-auto"],
            max_output_chars_per_message=1800,
            persistent_session=True,
        )
        return Settings(
            discord_token="test-token",
            allowed_guild_id=TEST_GUILD_ID,
            allowed_user_ids={TEST_USER_ID},
            config_path=root / "projects.json",
            data_dir=data_dir,
            codex_bin="codex",
            channels={TEST_CHANNEL_ID: project},
            max_concurrent_jobs_global=1,
            max_output_chunks=4,
            cancel_grace_seconds=5,
            log_level="INFO",
        )


if __name__ == "__main__":
    unittest.main()
