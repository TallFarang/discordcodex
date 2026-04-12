from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import normalize_project_name


@dataclass(frozen=True)
class RunPaths:
    metadata: Path
    prompt: Path
    log: Path


class LoggingStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    def create_run_paths(self, project_name: str) -> RunPaths:
        safe_name = normalize_project_name(project_name)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        log_dir = self.data_dir / "logs" / safe_name
        log_dir.mkdir(parents=True, exist_ok=True)
        return RunPaths(
            metadata=log_dir / f"{timestamp}.meta.json",
            prompt=log_dir / f"{timestamp}.prompt.txt",
            log=log_dir / f"{timestamp}.log",
        )

    def write_metadata(self, paths: RunPaths, metadata: dict) -> None:
        payload = dict(metadata)
        payload.setdefault("prompt_log", str(paths.prompt))
        payload.setdefault("log", str(paths.log))
        paths.metadata.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
