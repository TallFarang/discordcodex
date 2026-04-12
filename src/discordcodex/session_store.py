from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChannelSession:
    channel_id: str
    project_safe_name: str
    thread_id: str
    created_at: str
    updated_at: str
    last_log_path: str | None = None


class SessionStore:
    def __init__(self, data_dir: Path):
        self.session_dir = data_dir / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def load(self, channel_id: str) -> ChannelSession | None:
        path = self._path(channel_id)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            return ChannelSession(
                channel_id=str(payload["channel_id"]),
                project_safe_name=str(payload["project_safe_name"]),
                thread_id=str(payload["thread_id"]),
                created_at=str(payload["created_at"]),
                updated_at=str(payload["updated_at"]),
                last_log_path=payload.get("last_log_path"),
            )
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid session file: {path}") from exc

    def save(self, session: ChannelSession) -> None:
        path = self._path(session.channel_id)
        path.write_text(json.dumps(asdict(session), indent=2, sort_keys=True), encoding="utf-8")

    def clear(self, channel_id: str) -> bool:
        path = self._path(channel_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def _path(self, channel_id: str) -> Path:
        return self.session_dir / f"{channel_id}.json"
