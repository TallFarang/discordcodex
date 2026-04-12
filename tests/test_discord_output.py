import unittest

from discordcodex.discord_output import chunk_output, summarize_result


class DiscordOutputTests(unittest.TestCase):
    def test_chunk_output_respects_message_and_chunk_limits(self):
        chunks, truncated = chunk_output("abcdef", max_chars=2, max_chunks=2)

        self.assertEqual(chunks, ["ab", "cd"])
        self.assertTrue(truncated)

    def test_summarize_result_marks_cancelled_before_exit_code(self):
        summary = summarize_result(
            project_name="demo",
            exit_code=143,
            duration_seconds=3.2,
            log_path="data/logs/demo/run.log",
            cancelled=True,
            timed_out=False,
        )

        self.assertIn("Codex cancelled for `demo`.", summary)
        self.assertIn("Exit code: 143", summary)
        self.assertIn("Duration: 3s", summary)


if __name__ == "__main__":
    unittest.main()
