import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DockerEntrypointTests(unittest.TestCase):
    def test_single_github_token_writes_git_credentials_and_exports_gh_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            env = os.environ.copy()
            env.update(
                {
                    "DISCORDCODEX_GIT_USERNAME": "single-user",
                    "DISCORDCODEX_GITHUB_TOKEN": "single-token",
                    "DISCORDCODEX_DATA_DIR": str(data_dir),
                }
            )

            result = subprocess.run(
                [
                    str(ROOT / "docker-entrypoint.sh"),
                    "sh",
                    "-c",
                    "printf 'git=%s gh=%s source=%s' \"$GIT_CONFIG_GLOBAL\" \"${GH_TOKEN:-<missing>}\" \"${DISCORDCODEX_GITHUB_TOKEN:-<missing>}\"",
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
                "https://single-user:single-token@github.com\n",
            )
            self.assertIn(
                f"helper = store --file {credentials}",
                git_config.read_text(encoding="utf-8"),
            )
            self.assertEqual(result.stdout, f"git={git_config} gh=single-token source=<missing>")

    def test_single_github_token_file_writes_git_credentials_and_exports_gh_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            token_file = Path(tmp) / "github-token"
            token_file.write_text("single-file-token\n", encoding="utf-8")
            env = os.environ.copy()
            env.update(
                {
                    "DISCORDCODEX_GITHUB_TOKEN_FILE": str(token_file),
                    "DISCORDCODEX_DATA_DIR": str(data_dir),
                }
            )

            result = subprocess.run(
                [
                    str(ROOT / "docker-entrypoint.sh"),
                    "sh",
                    "-c",
                    "printf 'gh=%s file=%s' \"${GH_TOKEN:-<missing>}\" \"${DISCORDCODEX_GITHUB_TOKEN_FILE:-<missing>}\"",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            credentials = data_dir / "git-credentials"
            self.assertEqual(
                credentials.read_text(encoding="utf-8"),
                "https://x-access-token:single-file-token@github.com\n",
            )
            self.assertEqual(result.stdout, "gh=single-file-token file=<missing>")

    def test_single_github_token_takes_precedence_over_split_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            env = os.environ.copy()
            env.update(
                {
                    "DISCORDCODEX_GITHUB_TOKEN": "single-token",
                    "DISCORDCODEX_GIT_CREDENTIAL_TOKEN": "git-only-token",
                    "DISCORDCODEX_GITHUB_API_TOKEN": "api-only-token",
                    "DISCORDCODEX_DATA_DIR": str(data_dir),
                }
            )

            result = subprocess.run(
                [
                    str(ROOT / "docker-entrypoint.sh"),
                    "sh",
                    "-c",
                    "printf 'gh=%s git_source=%s api_source=%s' \"${GH_TOKEN:-<missing>}\" \"${DISCORDCODEX_GIT_CREDENTIAL_TOKEN:-<missing>}\" \"${DISCORDCODEX_GITHUB_API_TOKEN:-<missing>}\"",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            credentials = data_dir / "git-credentials"
            self.assertEqual(
                credentials.read_text(encoding="utf-8"),
                "https://x-access-token:single-token@github.com\n",
            )
            self.assertEqual(result.stdout, "gh=single-token git_source=<missing> api_source=<missing>")

    def test_missing_single_github_token_file_exits_with_clear_error(self):
        env = os.environ.copy()
        env.update({"DISCORDCODEX_GITHUB_TOKEN_FILE": "/missing/github-token"})

        result = subprocess.run(
            [str(ROOT / "docker-entrypoint.sh"), "sh", "-c", "true"],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Secret file not found: /missing/github-token", result.stderr)

    def test_writes_discordcodex_git_credentials_and_git_config_before_exec(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            env = os.environ.copy()
            env.update(
                {
                    "DISCORDCODEX_GIT_USERNAME": "test-github-user",
                    "DISCORDCODEX_GIT_CREDENTIAL_TOKEN": "test-github-token",
                    "DISCORDCODEX_DATA_DIR": str(data_dir),
                }
            )

            result = subprocess.run(
                [
                    str(ROOT / "docker-entrypoint.sh"),
                    "sh",
                    "-c",
                    "printf 'git=%s token=%s legacy=%s' \"$GIT_CONFIG_GLOBAL\" \"${DISCORDCODEX_GIT_CREDENTIAL_TOKEN:-<missing>}\" \"${GITHUB_TOKEN:-<missing>}\"",
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
            self.assertEqual(result.stdout, f"git={git_config} token=<missing> legacy=<missing>")

    def test_supports_legacy_github_token_alias_for_git_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            env = os.environ.copy()
            env.update(
                {
                    "GITHUB_USERNAME": "legacy-user",
                    "GITHUB_TOKEN": "legacy-token",
                    "DISCORDCODEX_DATA_DIR": str(data_dir),
                }
            )

            subprocess.run(
                [str(ROOT / "docker-entrypoint.sh"), "sh", "-c", "true"],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            credentials = data_dir / "git-credentials"
            self.assertEqual(
                credentials.read_text(encoding="utf-8"),
                "https://legacy-user:legacy-token@github.com\n",
            )

    def test_exports_gh_token_from_discordcodex_api_token_and_unsets_original(self):
        env = os.environ.copy()
        env.update({"DISCORDCODEX_GITHUB_API_TOKEN": "test-api-token"})

        result = subprocess.run(
            [
                str(ROOT / "docker-entrypoint.sh"),
                "sh",
                "-c",
                "printf 'gh=%s source=%s' \"${GH_TOKEN:-<missing>}\" \"${DISCORDCODEX_GITHUB_API_TOKEN:-<missing>}\"",
            ],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual(result.stdout, "gh=test-api-token source=<missing>")

    def test_reads_git_credential_token_from_file_and_does_not_export_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            token_file = Path(tmp) / "git-token"
            token_file.write_text("file-git-token\n", encoding="utf-8")
            env = os.environ.copy()
            env.update(
                {
                    "DISCORDCODEX_GIT_USERNAME": "file-user",
                    "DISCORDCODEX_GIT_CREDENTIAL_TOKEN_FILE": str(token_file),
                    "DISCORDCODEX_DATA_DIR": str(data_dir),
                }
            )

            result = subprocess.run(
                [
                    str(ROOT / "docker-entrypoint.sh"),
                    "sh",
                    "-c",
                    "printf 'file=%s token=%s' \"${DISCORDCODEX_GIT_CREDENTIAL_TOKEN_FILE:-<missing>}\" \"${DISCORDCODEX_GIT_CREDENTIAL_TOKEN:-<missing>}\"",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            credentials = data_dir / "git-credentials"
            self.assertEqual(
                credentials.read_text(encoding="utf-8"),
                "https://file-user:file-git-token@github.com\n",
            )
            self.assertEqual(result.stdout, "file=<missing> token=<missing>")

    def test_reads_github_api_token_from_file_and_does_not_export_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "api-token"
            token_file.write_text("file-api-token\n", encoding="utf-8")
            env = os.environ.copy()
            env.update({"DISCORDCODEX_GITHUB_API_TOKEN_FILE": str(token_file)})

            result = subprocess.run(
                [
                    str(ROOT / "docker-entrypoint.sh"),
                    "sh",
                    "-c",
                    "printf 'gh=%s file=%s source=%s' \"${GH_TOKEN:-<missing>}\" \"${DISCORDCODEX_GITHUB_API_TOKEN_FILE:-<missing>}\" \"${DISCORDCODEX_GITHUB_API_TOKEN:-<missing>}\"",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertEqual(result.stdout, "gh=file-api-token file=<missing> source=<missing>")


if __name__ == "__main__":
    unittest.main()
