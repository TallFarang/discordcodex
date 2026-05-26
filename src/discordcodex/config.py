from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SNOWFLAKE_RE = re.compile(r"^[0-9]{15,25}$")


@dataclass(frozen=True)
class ProjectConfig:
    channel_id: str
    name: str
    safe_name: str
    cwd: Path
    codex_home: Path | None
    timeout_seconds: int
    include_recent_messages: int
    codex_args: list[str]
    max_output_chars_per_message: int
    persistent_session: bool


@dataclass(frozen=True)
class GitHubProvisioningConfig:
    enabled: bool
    owner: str
    poll_interval_seconds: int
    run_on_startup: bool
    project_root: Path
    codex_home_root: Path
    codex_home_template: Path | None
    admin_channel_name: str
    discord_category_id: str | None
    include_archived: bool


@dataclass(frozen=True)
class Settings:
    discord_token: str
    allowed_guild_id: str
    allowed_user_ids: set[str]
    config_path: Path
    data_dir: Path
    codex_bin: str
    channels: dict[str, ProjectConfig]
    max_concurrent_jobs_global: int
    max_output_chunks: int
    cancel_grace_seconds: float
    log_level: str
    github_provisioning: GitHubProvisioningConfig | None = None


def load_settings(env: dict[str, str] | None = None, config_path: str | None = None) -> Settings:
    values = dict(os.environ if env is None else env)
    resolved_config_path = Path(
        config_path or values.get("DISCORDCODEX_CONFIG", "config/projects.json")
    ).expanduser()
    if not resolved_config_path.exists():
        raise ValueError(f"Config file does not exist: {resolved_config_path}")

    discord_token = _required(values, "DISCORD_TOKEN")
    allowed_guild_id = _required_snowflake(values, "ALLOWED_GUILD_ID")
    allowed_user_ids = _parse_user_ids(_required(values, "ALLOWED_USER_IDS"))
    data_dir = Path(values.get("DISCORDCODEX_DATA_DIR", "data")).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    _require_writable_dir(data_dir, "data directory")
    codex_bin = _resolve_codex_bin(values.get("CODEX_BIN", "codex"))

    with resolved_config_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError("Project config must be a JSON object")

    defaults = raw.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ValueError("Config defaults must be an object")
    raw_channels = raw.get("channels", {})
    if not isinstance(raw_channels, dict) or not raw_channels:
        raise ValueError("Config must define at least one channel")

    channels: dict[str, ProjectConfig] = {}
    safe_names: set[str] = set()
    base_dir = resolved_config_path.resolve().parent

    for channel_id, item in raw_channels.items():
        if not _is_snowflake(channel_id):
            raise ValueError(f"Invalid Discord channel ID: {channel_id}")
        if channel_id in channels:
            raise ValueError(f"Duplicate channel ID: {channel_id}")
        if not isinstance(item, dict):
            raise ValueError(f"Project config for channel {channel_id} must be an object")

        project = _build_project(channel_id, item, defaults, base_dir)
        if project.safe_name in safe_names:
            raise ValueError(f"Duplicate project name after normalization: {project.name}")
        safe_names.add(project.safe_name)
        channels[channel_id] = project

    github_provisioning = _build_github_provisioning(
        raw.get("github_provisioning"),
        base_dir,
    )

    return Settings(
        discord_token=discord_token,
        allowed_guild_id=allowed_guild_id,
        allowed_user_ids=allowed_user_ids,
        config_path=resolved_config_path.resolve(),
        data_dir=data_dir.resolve(),
        codex_bin=codex_bin,
        channels=channels,
        max_concurrent_jobs_global=_positive_int(
            raw.get("max_concurrent_jobs_global", defaults.get("max_concurrent_jobs_global", 2)),
            "max_concurrent_jobs_global",
        ),
        max_output_chunks=_positive_int(
            defaults.get("max_output_chunks", raw.get("max_output_chunks", 4)),
            "max_output_chunks",
        ),
        cancel_grace_seconds=float(defaults.get("cancel_grace_seconds", 5.0)),
        log_level=values.get("DISCORDCODEX_LOG_LEVEL", "INFO").upper(),
        github_provisioning=github_provisioning,
    )


def _build_project(
    channel_id: str,
    item: dict[str, Any],
    defaults: dict[str, Any],
    base_dir: Path,
) -> ProjectConfig:
    name = str(item.get("name", "")).strip()
    if not name:
        raise ValueError(f"Project for channel {channel_id} requires a name")
    safe_name = normalize_project_name(name)
    cwd_value = item.get("cwd")
    if not cwd_value:
        raise ValueError(f"Project {name} requires cwd")
    cwd = _resolve_path(str(cwd_value), base_dir)
    if not cwd.exists() or not cwd.is_dir():
        raise ValueError(f"cwd for project {name} must exist and be a directory: {cwd}")

    codex_home = None
    if item.get("codex_home"):
        codex_home = _resolve_path(str(item["codex_home"]), base_dir)
        codex_home.mkdir(parents=True, exist_ok=True)
        _require_writable_dir(codex_home, f"codex_home for {name}")

    timeout_seconds = _positive_int(
        item.get("timeout_seconds", defaults.get("timeout_seconds", 1800)),
        f"timeout_seconds for {name}",
    )
    include_recent_messages = int(
        item.get("include_recent_messages", defaults.get("include_recent_messages", 10))
    )
    if include_recent_messages < 0:
        raise ValueError(f"include_recent_messages for {name} must be non-negative")
    max_output_chars = _positive_int(
        item.get(
            "max_output_chars_per_message",
            defaults.get("max_output_chars_per_message", 1800),
        ),
        f"max_output_chars_per_message for {name}",
    )
    codex_args = item.get("codex_args", defaults.get("codex_args", ["--full-auto"]))
    if not isinstance(codex_args, list) or not all(isinstance(arg, str) for arg in codex_args):
        raise ValueError(f"codex_args for {name} must be a list of strings")
    persistent_session = bool(
        item.get("persistent_session", defaults.get("persistent_session", True))
    )

    return ProjectConfig(
        channel_id=channel_id,
        name=name,
        safe_name=safe_name,
        cwd=cwd.resolve(),
        codex_home=codex_home.resolve() if codex_home else None,
        timeout_seconds=timeout_seconds,
        include_recent_messages=include_recent_messages,
        codex_args=list(codex_args),
        max_output_chars_per_message=max_output_chars,
        persistent_session=persistent_session,
    )


def normalize_project_name(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    if not safe:
        raise ValueError(f"Project name cannot be normalized safely: {name}")
    return safe


def _build_github_provisioning(
    raw: Any,
    base_dir: Path,
) -> GitHubProvisioningConfig | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("github_provisioning must be an object")

    enabled = bool(raw.get("enabled", False))
    owner = str(raw.get("owner", "")).strip()
    if enabled and not owner:
        raise ValueError("github_provisioning.owner is required when provisioning is enabled")

    project_root_value = str(raw.get("project_root", "/projects"))
    codex_home_root_value = str(raw.get("codex_home_root", "/data/codex-home"))
    project_root = _resolve_path(project_root_value, base_dir)
    codex_home_root = _resolve_path(codex_home_root_value, base_dir)
    if enabled:
        project_root.mkdir(parents=True, exist_ok=True)
        codex_home_root.mkdir(parents=True, exist_ok=True)
        _require_writable_dir(project_root, "github_provisioning.project_root")
        _require_writable_dir(codex_home_root, "github_provisioning.codex_home_root")

    template = raw.get("codex_home_template")
    codex_home_template = _resolve_path(str(template), base_dir) if template else None

    category_id = raw.get("discord_category_id")
    if category_id is not None and not _is_snowflake(str(category_id)):
        raise ValueError("github_provisioning.discord_category_id must be a Discord snowflake ID")

    return GitHubProvisioningConfig(
        enabled=enabled,
        owner=owner,
        poll_interval_seconds=_positive_int(
            raw.get("poll_interval_seconds", 3600),
            "github_provisioning.poll_interval_seconds",
        ),
        run_on_startup=bool(raw.get("run_on_startup", True)),
        project_root=project_root.resolve(),
        codex_home_root=codex_home_root.resolve(),
        codex_home_template=codex_home_template.resolve() if codex_home_template else None,
        admin_channel_name=normalize_project_name(str(raw.get("admin_channel_name", "neo"))),
        discord_category_id=str(category_id) if category_id is not None else None,
        include_archived=bool(raw.get("include_archived", True)),
    )


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path


def _required(values: dict[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


def _required_snowflake(values: dict[str, str], key: str) -> str:
    value = _required(values, key)
    if not _is_snowflake(value):
        raise ValueError(f"{key} must be a Discord snowflake ID")
    return value


def _parse_user_ids(value: str) -> set[str]:
    user_ids = {part.strip() for part in value.split(",") if part.strip()}
    if not user_ids:
        raise ValueError("ALLOWED_USER_IDS must contain at least one user ID")
    invalid = sorted(user_id for user_id in user_ids if not _is_snowflake(user_id))
    if invalid:
        raise ValueError(f"Invalid Discord user ID(s): {', '.join(invalid)}")
    return user_ids


def _is_snowflake(value: str) -> bool:
    return bool(SNOWFLAKE_RE.match(str(value)))


def _positive_int(value: Any, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if number <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return number


def _require_writable_dir(path: Path, label: str) -> None:
    if not path.exists() or not path.is_dir():
        raise ValueError(f"{label} must be a directory: {path}")
    probe = path / ".discordcodex-write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise ValueError(f"{label} is not writable: {path}") from exc


def _resolve_codex_bin(value: str) -> str:
    if os.sep in value or (os.altsep and os.altsep in value):
        path = Path(value).expanduser()
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
        raise ValueError(f"CODEX_BIN is not executable: {path}")
    resolved = shutil.which(value)
    if resolved:
        return resolved
    raise ValueError(f"Codex binary not found on PATH: {value}")
