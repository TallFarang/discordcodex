import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DockerfileTests(unittest.TestCase):
    def test_dockerfile_installs_github_cli(self):
        content = (ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("cli.github.com", content)
        self.assertIn("apt-get install -y --no-install-recommends", content)
        self.assertIn("gh", content)


if __name__ == "__main__":
    unittest.main()
