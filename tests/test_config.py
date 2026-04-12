import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from discordcodex.config import load_settings


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
                            "111111111111111111": {
                                "name": "demo",
                                "cwd": "project",
                                "codex_home": "data/codex-home/demo",
                            }
                        },
                    }
                )
            )

            env = {
                "DISCORD_TOKEN": "token",
                "ALLOWED_GUILD_ID": "222222222222222222",
                "ALLOWED_USER_IDS": "333333333333333333,444444444444444444",
                "DISCORDCODEX_CONFIG": str(config_path),
                "DISCORDCODEX_DATA_DIR": str(data),
                "CODEX_BIN": str(codex_bin),
            }

            with patch.dict(os.environ, env, clear=True):
                settings = load_settings()

            channel = settings.channels["111111111111111111"]
            self.assertEqual(channel.name, "demo")
            self.assertEqual(channel.cwd, project.resolve())
            self.assertTrue(channel.codex_home.exists())
            self.assertEqual(settings.allowed_user_ids, {"333333333333333333", "444444444444444444"})

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
                            "111111111111111111": {"name": "My Project", "cwd": str(project)},
                            "222222222222222222": {"name": "my-project", "cwd": str(project)},
                        }
                    }
                )
            )

            env = {
                "DISCORD_TOKEN": "token",
                "ALLOWED_GUILD_ID": "333333333333333333",
                "ALLOWED_USER_IDS": "444444444444444444",
                "DISCORDCODEX_CONFIG": str(config_path),
                "CODEX_BIN": str(codex_bin),
            }

            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(ValueError, "Duplicate project name"):
                    load_settings()


if __name__ == "__main__":
    unittest.main()
