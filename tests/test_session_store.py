import tempfile
import unittest
from pathlib import Path

from discordcodex.session_store import ChannelSession, SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_saves_loads_and_clears_channel_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            session = ChannelSession(
                channel_id="100000000000000001",
                project_safe_name="demo",
                thread_id="019d8056-e1a1-7b20-a367-c7459e072546",
                created_at="2026-04-12T06:16:56+00:00",
                updated_at="2026-04-12T06:17:12+00:00",
                last_log_path="/data/logs/demo/run.log",
            )

            store.save(session)

            loaded = store.load("100000000000000001")
            self.assertEqual(loaded, session)

            self.assertTrue(store.clear("100000000000000001"))
            self.assertIsNone(store.load("100000000000000001"))
            self.assertFalse(store.clear("100000000000000001"))

    def test_rejects_malformed_session_file_with_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            session_file = root / "sessions" / "100000000000000001.json"
            session_file.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Invalid session file"):
                store.load("100000000000000001")


if __name__ == "__main__":
    unittest.main()
