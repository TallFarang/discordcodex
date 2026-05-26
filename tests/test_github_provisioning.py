import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from discordcodex.config import GitHubProvisioningConfig
from discordcodex.github_provisioning import GitHubProvisioner, GitHubRepo


class FakeRepoSource:
    def __init__(self, repos):
        self.repos = repos

    def list_repos(self, owner):
        return list(self.repos)


class FakeChannel:
    def __init__(self, channel_id, name):
        self.id = int(channel_id)
        self.name = name
        self.sent = []

    async def send(self, content):
        self.sent.append(content)


class FakeGuild:
    def __init__(self):
        self.text_channels = []
        self.next_channel_id = 100000000000000010

    async def create_text_channel(self, name, category=None):
        channel = FakeChannel(self.next_channel_id, name)
        self.next_channel_id += 1
        self.text_channels.append(channel)
        return channel


class FakeDiscordClient:
    def get_channel(self, channel_id):
        return None


class GitHubProvisioningTests(unittest.TestCase):
    def test_provisions_missing_repo_channel_codex_home_and_config(self):
        asyncio.run(self._provisions_missing_repo())

    async def _provisions_missing_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "projects.json"
            existing_project = root / "projects" / "existing"
            existing_project.mkdir(parents=True)
            template = root / "codex-template"
            template.mkdir()
            (template / "config.toml").write_text('model = "gpt-5-codex"\n', encoding="utf-8")
            repo_checkout = root / "projects" / "new-repo"
            (repo_checkout / ".git").mkdir(parents=True)
            config_path.write_text(
                json.dumps(
                    {
                        "channels": {
                            "100000000000000001": {
                                "name": "existing",
                                "cwd": str(existing_project),
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            config = GitHubProvisioningConfig(
                enabled=True,
                owner="TallFarang",
                poll_interval_seconds=3600,
                run_on_startup=True,
                project_root=root / "projects",
                codex_home_root=root / "codex-home",
                codex_home_template=template,
                admin_channel_name="neo",
                discord_category_id=None,
                include_archived=False,
            )
            guild = FakeGuild()
            provisioner = GitHubProvisioner(
                config=config,
                config_path=config_path,
                discord_client=FakeDiscordClient(),
                repo_source=FakeRepoSource(
                    [
                        GitHubRepo("existing", "TallFarang/existing"),
                        GitHubRepo("new-repo", "TallFarang/new-repo"),
                    ]
                ),
            )

            report = await provisioner.run_for_guild(guild, {"existing"})

            self.assertEqual(report.created, ["new-repo -> #new-repo"])
            self.assertIn("existing: already configured", report.skipped)
            self.assertEqual([channel.name for channel in guild.text_channels], ["neo", "new-repo"])
            self.assertIn("Created:", guild.text_channels[0].sent[0])
            self.assertTrue((root / "codex-home" / "new-repo" / "config.toml").exists())
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            new_channel = payload["channels"]["100000000000000011"]
            self.assertEqual(new_channel["name"], "new-repo")
            self.assertEqual(new_channel["cwd"], str(repo_checkout))
            self.assertEqual(new_channel["codex_home"], str(root / "codex-home" / "new-repo"))


if __name__ == "__main__":
    unittest.main()
