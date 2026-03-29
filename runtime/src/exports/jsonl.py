from __future__ import annotations

import json
from datetime import datetime, timezone

from db.connection import EXPORT_ROOT


def append_event_mirror(record: dict) -> str:
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = EXPORT_ROOT / f"task-events-{stamp}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return str(path)
