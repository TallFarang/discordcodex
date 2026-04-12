import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DockerEntrypointTests(unittest.TestCase):
    def test_writes_github_credentials_and_git_config_before_exec(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            env = os.environ.copy()
            env.update(
                {
                    "GITHUB_USERNAME": "test-github-user",
                    "GITHUB_TOKEN": "test-github-token",
                    "DISCORDCODEX_DATA_DIR": str(data_dir),
                }
            )

            result = subprocess.run(
                [
                    str(ROOT / "docker-entrypoint.sh"),
                    "sh",
                    "-c",
                    "printf 'git=%s token=%s' \"$GIT_CONFIG_GLOBAL\" \"${GITHUB_TOKEN:-<missing>}\"",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            credentials = data_dir / "git-credentials"
            git_config = data_dir / "gitconfig"
            self.assertEqual(
                credentials.read_text(encoding="utf-8"),
                "https://test-github-user:test-github-token@github.com\n",
            )
            self.assertIn(
                f"helper = store --file {credentials}",
                git_config.read_text(encoding="utf-8"),
            )
            self.assertEqual(result.stdout, f"git={git_config} token=<missing>")


if __name__ == "__main__":
    unittest.main()
