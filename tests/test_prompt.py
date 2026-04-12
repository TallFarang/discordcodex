import unittest
from pathlib import Path

from discordcodex.config import ProjectConfig
from discordcodex.prompt import ChannelMessage, build_prompt


TEST_CHANNEL_ID = "100000000000000001"


class PromptTests(unittest.TestCase):
    def test_build_prompt_separates_metadata_recent_context_and_request(self):
        project = ProjectConfig(
            channel_id=TEST_CHANNEL_ID,
            name="demo",
            safe_name="demo",
            cwd=Path("/projects/demo"),
            codex_home=None,
            timeout_seconds=30,
            include_recent_messages=2,
            codex_args=["--full-auto"],
            max_output_chars_per_message=1800,
            persistent_session=True,
        )
        prompt = build_prompt(
            project,
            "general",
            [
                ChannelMessage(author="alice", content="first", is_bot=False),
                ChannelMessage(author="bot", content="Codex output", is_bot=True),
                ChannelMessage(author="alice", content="second", is_bot=False),
            ],
            "fix tests",
        )

        self.assertIn("Project: demo", prompt)
        self.assertIn("Working directory: /projects/demo", prompt)
        self.assertIn("Discord channel: general", prompt)
        self.assertIn("alice: first", prompt)
        self.assertIn("alice: second", prompt)
        self.assertNotIn("Codex output", prompt)
        self.assertTrue(prompt.rstrip().endswith("fix tests"))

    def test_build_resume_prompt_omits_recent_context(self):
        project = ProjectConfig(
            channel_id=TEST_CHANNEL_ID,
            name="demo",
            safe_name="demo",
            cwd=Path("/projects/demo"),
            codex_home=None,
            timeout_seconds=30,
            include_recent_messages=2,
            codex_args=["--full-auto"],
            max_output_chars_per_message=1800,
            persistent_session=True,
        )

        prompt = build_prompt(
            project,
            "general",
            [ChannelMessage(author="alice", content="old context", is_bot=False)],
            "continue work",
            resumed_session=True,
        )

        self.assertIn("Resuming existing Codex conversation.", prompt)
        self.assertNotIn("old context", prompt)
        self.assertTrue(prompt.rstrip().endswith("continue work"))


if __name__ == "__main__":
    unittest.main()
