import unittest
from pathlib import Path

from discordcodex.config import ProjectConfig
from discordcodex.prompt import ChannelMessage, build_prompt


class PromptTests(unittest.TestCase):
    def test_build_prompt_separates_metadata_recent_context_and_request(self):
        project = ProjectConfig(
            channel_id="111111111111111111",
            name="demo",
            safe_name="demo",
            cwd=Path("/projects/demo"),
            codex_home=None,
            timeout_seconds=30,
            include_recent_messages=2,
            codex_args=["--full-auto"],
            max_output_chars_per_message=1800,
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


if __name__ == "__main__":
    unittest.main()
