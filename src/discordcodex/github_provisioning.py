from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .config import GitHubProvisioningConfig, normalize_project_name
from .discord_output import chunk_output


@dataclass(frozen=True)
class GitHubRepo:
    name: str
    name_with_owner: str
    is_archived: bool = False

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.name_with_owner}.git"


@dataclass
class ProvisioningReport:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def message(self) -> str:
        lines = ["GitHub poll complete."]
        if self.created:
            lines.append("")
            lines.append("Created:")
            lines.extend(f"- {item}" for item in self.created)
        if self.skipped:
            lines.append("")
            lines.append("Skipped:")
            lines.extend(f"- {item}" for item in self.skipped)
        if self.errors:
            lines.append("")
            lines.append("Errors:")
            lines.extend(f"- {item}" for item in self.errors)
        if not self.created and not self.skipped and not self.errors:
            lines.append("No repositories found.")
        return "\n".join(lines)


class RepoSource(Protocol):
    def list_repos(self, owner: str) -> list[GitHubRepo]:
        ...


class GhCliRepoSource:
    def list_repos(self, owner: str) -> list[GitHubRepo]:
        result = subprocess.run(
            [
                "gh",
                "repo",
                "list",
                owner,
                "--limit",
                "1000",
                "--json",
                "name,nameWithOwner,isArchived",
            ],
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        repos = []
        for item in payload:
            repos.append(
                GitHubRepo(
                    name=str(item["name"]),
                    name_with_owner=str(item["nameWithOwner"]),
                    is_archived=bool(item.get("isArchived", False)),
                )
            )
        return repos


class GitHubProvisioner:
    def __init__(
        self,
        config: GitHubProvisioningConfig,
        config_path: Path,
        discord_client,
        repo_source: RepoSource | None = None,
    ):
        self.config = config
        self.config_path = config_path
        self.discord_client = discord_client
        self.repo_source = repo_source or GhCliRepoSource()

    async def run_for_guild(self, guild, existing_project_names: set[str]) -> ProvisioningReport:
        report = ProvisioningReport()
        try:
            admin_channel = await self._find_or_create_channel(guild, self.config.admin_channel_name)
        except Exception as exc:
            report.errors.append(f"{self.config.admin_channel_name}: could not create admin channel: {exc}")
            return report

        try:
            repos = await asyncio.to_thread(self.repo_source.list_repos, self.config.owner)
        except Exception as exc:
            report.errors.append(f"could not list GitHub repos for {self.config.owner}: {exc}")
            await self._send_report(admin_channel, report)
            return report

        configured_names = {normalize_project_name(name) for name in existing_project_names}
        for repo in repos:
            repo_safe_name = normalize_project_name(repo.name)
            if repo.is_archived and not self.config.include_archived:
                report.skipped.append(f"{repo.name}: archived")
                continue
            if repo_safe_name in configured_names:
                report.skipped.append(f"{repo.name}: already configured")
                continue
            try:
                channel = await self._find_or_create_channel(guild, repo_safe_name)
                cwd = await asyncio.to_thread(self._ensure_project_checkout, repo)
                codex_home = await asyncio.to_thread(self._ensure_codex_home, repo_safe_name)
                await asyncio.to_thread(self._append_project_config, str(channel.id), repo.name, cwd, codex_home)
                configured_names.add(repo_safe_name)
                report.created.append(f"{repo.name} -> #{channel.name}")
            except Exception as exc:
                report.errors.append(f"{repo.name}: {exc}")

        await self._send_report(admin_channel, report)
        return report

    async def _find_or_create_channel(self, guild, name: str):
        safe_name = normalize_project_name(name)
        for channel in getattr(guild, "text_channels", []):
            if getattr(channel, "name", "") == safe_name:
                return channel
        category = None
        if self.config.discord_category_id:
            category = self.discord_client.get_channel(int(self.config.discord_category_id))
        return await guild.create_text_channel(safe_name, category=category)

    def _ensure_project_checkout(self, repo: GitHubRepo) -> Path:
        target = self.config.project_root / repo.name
        if target.exists():
            if (target / ".git").exists():
                return target
            if any(target.iterdir()):
                raise RuntimeError(f"{target} already exists and is not an empty git checkout")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", repo.clone_url, str(target)], check=True)
        return target

    def _ensure_codex_home(self, safe_name: str) -> Path:
        target = self.config.codex_home_root / safe_name
        if target.exists():
            return target
        if self.config.codex_home_template:
            if not self.config.codex_home_template.exists():
                raise RuntimeError(f"codex home template does not exist: {self.config.codex_home_template}")
            shutil.copytree(self.config.codex_home_template, target)
        else:
            target.mkdir(parents=True)
        return target

    def _append_project_config(
        self,
        channel_id: str,
        repo_name: str,
        cwd: Path,
        codex_home: Path,
    ) -> None:
        with self.config_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        channels = payload.setdefault("channels", {})
        if channel_id in channels:
            return
        channels[channel_id] = {
            "name": repo_name,
            "cwd": str(cwd),
            "codex_home": str(codex_home),
        }
        tmp_path = self.config_path.with_suffix(self.config_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        with tmp_path.open("r", encoding="utf-8") as f:
            json.load(f)
        tmp_path.replace(self.config_path)

    async def _send_report(self, channel, report: ProvisioningReport) -> None:
        chunks, truncated = chunk_output(report.message(), max_chars=1800, max_chunks=4)
        for chunk in chunks:
            await channel.send(chunk)
        if truncated:
            await channel.send("GitHub poll report truncated.")
