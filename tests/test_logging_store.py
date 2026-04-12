import json
import tempfile
import unittest
from pathlib import Path

from discordcodex.logging_store import LoggingStore


class LoggingStoreTests(unittest.TestCase):
    def test_writes_redacted_metadata_prompt_and_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LoggingStore(Path(tmp))
            paths = store.create_run_paths("My Project")
            paths.prompt.write_text("secret prompt")
            paths.log.write_text("codex output")
            store.write_metadata(
                paths,
                {
                    "project": "My Project",
                    "command": ["codex", "exec", "<prompt redacted>"],
                    "exit_code": 0,
                },
            )

            metadata = json.loads(paths.metadata.read_text())
            self.assertEqual(metadata["prompt_log"], str(paths.prompt))
            self.assertEqual(metadata["log"], str(paths.log))
            self.assertEqual(metadata["command"][-1], "<prompt redacted>")
            self.assertEqual(paths.log.read_text(), "codex output")


if __name__ == "__main__":
    unittest.main()
