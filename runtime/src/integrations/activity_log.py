from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from db.connection import REPO_ROOT

ACTIVITY_LOG_PATH = REPO_ROOT / "logs" / "activity-log.json"


def _tokyo_now() -> datetime:
    return datetime.now().astimezone().astimezone(timezone.utc).astimezone()


def _read_entries(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def append_activity_entry(entry: dict, log_path: str | Path | None = None) -> dict:
    path = Path(log_path) if log_path else ACTIVITY_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = _read_entries(path)
    entries.append(entry)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return entry


def build_manual_entry(
    *,
    agent_name: str,
    department: str,
    task_description: str,
    status: str,
    output_level: str = "高",
) -> dict:
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now().astimezone()
    return {
        "id": str(uuid.uuid4()),
        "timestamp": now_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "date": now_local.strftime("%Y-%m-%d"),
        "time": now_local.strftime("%H:%M"),
        "agent": agent_name,
        "department": department,
        "task": task_description,
        "status": status,
        "output_level": output_level,
    }


def _status_for_event(event_type: str) -> str:
    return {
        "task.created": "登録",
        "task.completed": "完了",
        "task.failed": "失敗",
        "task.timeout": "タイムアウト",
        "approval.requested": "要承認",
    }.get(event_type, event_type)


def deliver_notification(notification: dict, log_path: str | Path | None = None) -> dict:
    payload = notification["payload"]
    task = payload.get("task", {})
    agent = payload.get("agent", {})
    event = payload.get("event", {})
    entry = build_manual_entry(
        agent_name=agent.get("name", task.get("agent_id", "")),
        department=agent.get("department_name", ""),
        task_description=task.get("title", event.get("event_type", "")),
        status=_status_for_event(event.get("event_type", "")),
        output_level={"high": "高", "normal": "中", "low": "低"}.get(task.get("priority", "normal"), "中"),
    )
    entry["task_id"] = task.get("task_id", "")
    entry["event_type"] = event.get("event_type", "")
    entry["workflow_id"] = task.get("workflow_id", "")
    append_activity_entry(entry, log_path=log_path)
    return {
        "status": "sent",
        "external_id": entry["id"],
        "detail": {"path": str(log_path or ACTIVITY_LOG_PATH)},
    }

