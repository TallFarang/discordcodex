import tempfile
import unittest
from pathlib import Path

from discordcodex.guide_store import GuideStore


TEST_CHANNEL_ID = "100000000000000001"


class GuideStoreTests(unittest.TestCase):
    def test_marks_channel_guide_as_sent_persistently(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            store = GuideStore(data_dir)

            self.assertTrue(store.mark_sent_if_first(TEST_CHANNEL_ID))
            self.assertFalse(store.mark_sent_if_first(TEST_CHANNEL_ID))

            restarted = GuideStore(data_dir)
            self.assertFalse(restarted.mark_sent_if_first(TEST_CHANNEL_ID))


if __name__ == "__main__":
    unittest.main()
