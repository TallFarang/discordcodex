import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_EXAMPLE_FILES = [
    ROOT / "README.md",
    ROOT / "config" / "projects.example.json",
    ROOT / "docker-compose.example.yml",
    ROOT / "docs" / "SPEC.md",
]


class PublicShareTests(unittest.TestCase):
    def test_public_examples_do_not_contain_personal_setup_references(self):
        forbidden = [
            "le" + "wis",
            "/" + "users/",
            "q" + "nap",
        ]

        for path in PUBLIC_EXAMPLE_FILES:
            with self.subTest(path=path.relative_to(ROOT)):
                content = path.read_text(encoding="utf-8").lower()
                for term in forbidden:
                    self.assertNotIn(term, content)

    def test_public_examples_use_symbolic_discord_id_placeholders(self):
        placeholder_snowflake = re.compile(r"\b([1-9])\1{14,24}\b")

        for path in PUBLIC_EXAMPLE_FILES:
            with self.subTest(path=path.relative_to(ROOT)):
                content = path.read_text(encoding="utf-8")
                self.assertIsNone(placeholder_snowflake.search(content))


if __name__ == "__main__":
    unittest.main()
