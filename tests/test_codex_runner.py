import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from discordcodex.codex_runner import CodexProgress, CodexRunner
from discordcodex.config import ProjectConfig


TEST_CHANNEL_ID = "100000000000000001"


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
                "for name in ('CODEX_HOME', 'DISCORD_TOKEN', 'GITHUB_TOKEN', 'DISCORDCODEX_GITHUB_TOKEN', 'DISCORDCODEX_GITHUB_API_TOKEN', 'GIT_CONFIG_GLOBAL', 'GH_TOKEN'):\n"
                "    print(f'{name}=' + os.environ.get(name, '<missing>'))\n"
            )
            project = ProjectConfig(
                channel_id=TEST_CHANNEL_ID,
                name="demo",
                safe_name="demo",
                cwd=project_dir,
                codex_home=root / "codex-home",
                timeout_seconds=5,
                include_recent_messages=0,
                codex_args=["--full-auto"],
                max_output_chars_per_message=1800,
                persistent_session=True,
            )
            with patch.dict(
                os.environ,
                {
                    "DISCORD_TOKEN": "test-discord-token",
                    "GITHUB_TOKEN": "test-github-token",
                    "DISCORDCODEX_GITHUB_TOKEN": "test-discordcodex-github-token",
                    "DISCORDCODEX_GITHUB_API_TOKEN": "test-discordcodex-api-token",
                    "GH_TOKEN": "test-gh-token",
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
            self.assertIn("GH_TOKEN=test-gh-token", result.output)
            self.assertIn("DISCORD_TOKEN=<missing>", result.output)
            self.assertIn("GITHUB_TOKEN=<missing>", result.output)
            self.assertIn("DISCORDCODEX_GITHUB_TOKEN=<missing>", result.output)
            self.assertIn("DISCORDCODEX_GITHUB_API_TOKEN=<missing>", result.output)

    def test_parses_json_thread_id_and_assistant_response(self):
        asyncio.run(self._run_fake_codex_json())

    async def _run_fake_codex_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "project"
            project_dir.mkdir()
            fake_codex = root / "fake_codex.py"
            fake_codex.write_text(
                "import json, sys\n"
                "print(json.dumps({'type': 'thread.started', 'thread_id': '019d8056-e1a1-7b20-a367-c7459e072546'}))\n"
                "print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'hello from codex'}}))\n"
            )
            project = ProjectConfig(
                channel_id=TEST_CHANNEL_ID,
                name="demo",
                safe_name="demo",
                cwd=project_dir,
                codex_home=None,
                timeout_seconds=5,
                include_recent_messages=0,
                codex_args=["--full-auto"],
                max_output_chars_per_message=1800,
                persistent_session=True,
            )
            runner = CodexRunner(codex_bin=os.sys.executable)

            result = await runner.run(
                project=project,
                prompt="hello",
                extra_args=[str(fake_codex)],
                timeout_seconds=5,
            )

            self.assertEqual(result.thread_id, "019d8056-e1a1-7b20-a367-c7459e072546")
            self.assertEqual(result.assistant_response, "hello from codex")

    def test_builds_resume_command_with_session_id(self):
        asyncio.run(self._run_fake_codex_resume())

    async def _run_fake_codex_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "project"
            project_dir.mkdir()
            fake_codex = root / "fake_codex.py"
            fake_codex.write_text(
                "import sys\n"
                "print('args=' + ' '.join(sys.argv[1:-1]))\n"
                "print('prompt=' + sys.argv[-1])\n"
            )
            project = ProjectConfig(
                channel_id=TEST_CHANNEL_ID,
                name="demo",
                safe_name="demo",
                cwd=project_dir,
                codex_home=None,
                timeout_seconds=5,
                include_recent_messages=0,
                codex_args=["--full-auto"],
                max_output_chars_per_message=1800,
                persistent_session=True,
            )
            runner = CodexRunner(codex_bin=os.sys.executable)

            result = await runner.run(
                project=project,
                prompt="continue",
                session_id="019d8056-e1a1-7b20-a367-c7459e072546",
                extra_args=[str(fake_codex)],
                timeout_seconds=5,
            )

            self.assertIn("args=exec resume --json --full-auto 019d8056-e1a1-7b20-a367-c7459e072546", result.output)
            self.assertIn("prompt=continue", result.output)

    def test_streams_progress_callback_and_preserves_complete_output(self):
        asyncio.run(self._stream_progress_and_output())

    async def _stream_progress_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "project"
            project_dir.mkdir()
            fake_codex = root / "fake_codex.py"
            fake_codex.write_text(
                "import json, sys, time\n"
                "print(json.dumps({'type': 'item.started', 'item': {'type': 'tool_call', 'name': 'shell_command'}}), flush=True)\n"
                "time.sleep(0.05)\n"
                "print('not json', flush=True)\n"
                "print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'done'}}), flush=True)\n",
                encoding="utf-8",
            )
            project = ProjectConfig(
                channel_id=TEST_CHANNEL_ID,
                name="demo",
                safe_name="demo",
                cwd=project_dir,
                codex_home=None,
                timeout_seconds=5,
                include_recent_messages=0,
                codex_args=["--full-auto"],
                max_output_chars_per_message=1800,
                persistent_session=True,
            )
            runner = CodexRunner(codex_bin=os.sys.executable)
            progress_events: list[CodexProgress] = []

            async def progress_callback(progress: CodexProgress) -> None:
                progress_events.append(progress)

            result = await runner.run(
                project=project,
                prompt="hello",
                extra_args=[str(fake_codex)],
                timeout_seconds=5,
                progress_callback=progress_callback,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("not json", result.output)
            self.assertEqual(result.assistant_response, "done")
            self.assertIn(
                CodexProgress(message="Codex is running a command...", kind="command"),
                progress_events,
            )
            self.assertIn(
                CodexProgress(message="Codex is preparing a response...", kind="response"),
                progress_events,
            )

    def test_timeout_preserves_partial_streamed_output(self):
        asyncio.run(self._timeout_preserves_partial_output())

    async def _timeout_preserves_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "project"
            project_dir.mkdir()
            fake_codex = root / "fake_codex.py"
            fake_codex.write_text(
                "import time\n"
                "print('before timeout', flush=True)\n"
                "time.sleep(10)\n",
                encoding="utf-8",
            )
            project = ProjectConfig(
                channel_id=TEST_CHANNEL_ID,
                name="demo",
                safe_name="demo",
                cwd=project_dir,
                codex_home=None,
                timeout_seconds=1,
                include_recent_messages=0,
                codex_args=["--full-auto"],
                max_output_chars_per_message=1800,
                persistent_session=True,
            )
            runner = CodexRunner(codex_bin=os.sys.executable, cancel_grace_seconds=0.2)

            result = await runner.run(
                project=project,
                prompt="hello",
                extra_args=[str(fake_codex)],
                timeout_seconds=1,
            )

            self.assertTrue(result.timed_out)
            self.assertIn("before timeout", result.output)


if __name__ == "__main__":
    unittest.main()
