import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from discordcodex.codex_runner import CodexRunner
from discordcodex.config import ProjectConfig


class CodexRunnerTests(unittest.TestCase):
    def test_runs_fake_codex_in_project_directory(self):
        asyncio.run(self._run_fake_codex())

    async def _run_fake_codex(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "project"
            project_dir.mkdir()
            fake_codex = root / "fake_codex.py"
            fake_codex.write_text(
                "import os, sys\n"
                "print('cwd=' + os.getcwd())\n"
                "print('args=' + ' '.join(sys.argv[1:-1]))\n"
                "print('prompt=' + sys.argv[-1])\n"
                "for name in ('CODEX_HOME', 'DISCORD_TOKEN', 'GITHUB_TOKEN', 'GIT_CONFIG_GLOBAL'):\n"
                "    print(f'{name}=' + os.environ.get(name, '<missing>'))\n"
            )
            project = ProjectConfig(
                channel_id="111111111111111111",
                name="demo",
                safe_name="demo",
                cwd=project_dir,
                codex_home=root / "codex-home",
                timeout_seconds=5,
                include_recent_messages=0,
                codex_args=["--full-auto"],
                max_output_chars_per_message=1800,
            )
            with patch.dict(
                os.environ,
                {
                    "DISCORD_TOKEN": "discord-secret",
                    "GITHUB_TOKEN": "github-secret",
                    "GIT_CONFIG_GLOBAL": str(root / "gitconfig"),
                },
                clear=False,
            ):
                runner = CodexRunner(codex_bin=os.sys.executable)

                result = await runner.run(
                    project=project,
                    prompt="hello",
                    extra_args=[str(fake_codex), "exec"],
                    timeout_seconds=5,
                )

            self.assertEqual(result.exit_code, 0)
            self.assertIn(f"cwd={project_dir.resolve()}", result.output)
            self.assertIn("args=", result.output)
            self.assertIn("prompt=hello", result.output)
            self.assertIn(f"CODEX_HOME={root / 'codex-home'}", result.output)
            self.assertIn(f"GIT_CONFIG_GLOBAL={root / 'gitconfig'}", result.output)
            self.assertIn("DISCORD_TOKEN=<missing>", result.output)
            self.assertIn("GITHUB_TOKEN=<missing>", result.output)


if __name__ == "__main__":
    unittest.main()
