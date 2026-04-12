import unittest

from discordcodex.discord_output import (
    chunk_output,
    extract_assistant_response,
    help_message,
    summarize_result,
)


class DiscordOutputTests(unittest.TestCase):
    def test_chunk_output_respects_message_and_chunk_limits(self):
        chunks, truncated = chunk_output("abcdef", max_chars=2, max_chunks=2)

        self.assertEqual(chunks, ["ab", "cd"])
        self.assertTrue(truncated)

    def test_help_message_is_generic_usage_guide(self):
        message = help_message()

        self.assertIn("DiscordCodex is ready.", message)
        self.assertIn("Send a normal message here", message)
        self.assertIn("`!status`", message)
        self.assertIn("`!cancel`", message)
        self.assertIn("`!tail`", message)
        self.assertIn("`!projects`", message)
        self.assertIn("`!help`", message)
        self.assertNotIn("/projects/", message)

    def test_summarize_result_marks_cancelled_before_exit_code(self):
        summary = summarize_result(
            project_name="demo",
            exit_code=143,
            duration_seconds=3.2,
            log_path="data/logs/demo/run.log",
            cancelled=True,
            timed_out=False,
        )

        self.assertEqual(summary, "Codex cancelled for `demo`. Use `!tail` for details.")

    def test_extract_assistant_response_from_codex_transcript(self):
        transcript = """Reading additional input from stdin...
OpenAI Codex v0.120.0 (research preview)
--------
user
Hey
warning: Codex could not find bubblewrap on PATH.
codex
Hey. What do you want to work on in /projects/discordcodex?
tokens used
320
"""

        self.assertEqual(
            extract_assistant_response(transcript),
            "Hey. What do you want to work on in /projects/discordcodex?",
        )

    def test_extract_assistant_response_returns_none_without_clean_answer(self):
        transcript = "OpenAI Codex v0.120.0\nuser\nHey\ntokens used\n320\n"

        self.assertIsNone(extract_assistant_response(transcript))


if __name__ == "__main__":
    unittest.main()
