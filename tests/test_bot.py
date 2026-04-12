import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from discordcodex.bot import DiscordCodexClient
from discordcodex.config import ProjectConfig, Settings
from discordcodex.session_store import ChannelSession, SessionStore


TEST_CHANNEL_ID = "100000000000000001"
TEST_GUILD_ID = "100000000000000002"
TEST_USER_ID = "100000000000000003"


class FakeChannel:
    def __init__(self, channel_id=TEST_CHANNEL_ID):
        self.id = int(channel_id)
        self.sent = []

    async def send(self, content):
        self.sent.append(content)


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


if __name__ == "__main__":
    unittest.main()
