import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from discordcodex.config import load_settings


TEST_CHANNEL_ID = "100000000000000001"
TEST_OTHER_CHANNEL_ID = "100000000000000002"
TEST_GUILD_ID = "100000000000000003"
TEST_USER_ID = "100000000000000004"
TEST_OTHER_USER_ID = "100000000000000005"


class ConfigTests(unittest.TestCase):
    def test_loads_projects_and_resolves_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            data = root / "data"
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n")
            codex_bin.chmod(0o755)
            config_path = root / "projects.json"
            config_path.write_text(
                json.dumps(
                    {
                        "defaults": {"timeout_seconds": 10},
                        "channels": {
                            TEST_CHANNEL_ID: {
                                "name": "demo",
                                "cwd": "project",
                                "codex_home": "data/codex-home/demo",
                            }
                        },
                    }
                )
            )

            env = {
                "DISCORD_TOKEN": "test-discord-token",
                "ALLOWED_GUILD_ID": TEST_GUILD_ID,
                "ALLOWED_USER_IDS": f"{TEST_USER_ID},{TEST_OTHER_USER_ID}",
                "DISCORDCODEX_CONFIG": str(config_path),
                "DISCORDCODEX_DATA_DIR": str(data),
                "CODEX_BIN": str(codex_bin),
            }

            with patch.dict(os.environ, env, clear=True):
                settings = load_settings()

            channel = settings.channels[TEST_CHANNEL_ID]
            self.assertEqual(channel.name, "demo")
            self.assertEqual(channel.cwd, project.resolve())
            self.assertTrue(channel.codex_home.exists())
            self.assertTrue(channel.persistent_session)
            self.assertEqual(settings.allowed_user_ids, {TEST_USER_ID, TEST_OTHER_USER_ID})

    def test_loads_project_level_persistent_session_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            data = root / "data"
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n")
            codex_bin.chmod(0o755)
            config_path = root / "projects.json"
            config_path.write_text(
                json.dumps(
                    {
                        "channels": {
                            TEST_CHANNEL_ID: {
                                "name": "demo",
                                "cwd": "project",
                                "persistent_session": False,
                            }
                        },
                    }
                )
            )

            env = {
                "DISCORD_TOKEN": "test-discord-token",
                "ALLOWED_GUILD_ID": TEST_GUILD_ID,
                "ALLOWED_USER_IDS": TEST_USER_ID,
                "DISCORDCODEX_CONFIG": str(config_path),
                "DISCORDCODEX_DATA_DIR": str(data),
                "CODEX_BIN": str(codex_bin),
            }

            with patch.dict(os.environ, env, clear=True):
                settings = load_settings()

            self.assertFalse(settings.channels[TEST_CHANNEL_ID].persistent_session)

    def test_rejects_duplicate_normalized_project_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            codex_bin = root / "codex"
            codex_bin.write_text("#!/bin/sh\nexit 0\n")
            codex_bin.chmod(0o755)
            config_path = root / "projects.json"
            config_path.write_text(
                json.dumps(
                    {
                        "channels": {
                            TEST_CHANNEL_ID: {"name": "My Project", "cwd": str(project)},
                            TEST_OTHER_CHANNEL_ID: {"name": "my-project", "cwd": str(project)},
                        }
                    }
                )
            )

            env = {
                "DISCORD_TOKEN": "test-discord-token",
                "ALLOWED_GUILD_ID": TEST_GUILD_ID,
                "ALLOWED_USER_IDS": TEST_USER_ID,
                "DISCORDCODEX_CONFIG": str(config_path),
                "CODEX_BIN": str(codex_bin),
            }

            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(ValueError, "Duplicate project name"):
                    load_settings()


if __name__ == "__main__":
    unittest.main()
