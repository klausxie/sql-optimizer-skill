from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io_utils import append_jsonl


def log_event(manifest_path: Path, stage: str, event: str, payload: dict[str, Any]) -> None:
    append_jsonl(
        manifest_path,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "event": event,
            "payload": payload,
        },
    )
