from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class GuideStore:
    def __init__(self, data_dir: Path):
        self.guide_dir = data_dir / "guides"
        self.guide_dir.mkdir(parents=True, exist_ok=True)

    def mark_sent_if_first(self, channel_id: str) -> bool:
        path = self._path(channel_id)
        if path.exists():
            return False
        payload = {
            "channel_id": str(channel_id),
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return True

    def _path(self, channel_id: str) -> Path:
        return self.guide_dir / f"{channel_id}.json"
