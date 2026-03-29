from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib import request

from activity_log import ACTIVITY_LOG_PATH
from config import load_virtual_team_env


def _api_call(api_key: str, database_id: str, payload: dict) -> dict:
    req = request.Request(
        "https://api.notion.com/v1/pages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _page_payload(database_id: str, *, agent: str, department: str, task: str, status: str, date: str) -> dict:
    return {
        "parent": {"database_id": database_id},
        "properties": {
            "Agent": {"title": [{"text": {"content": agent}}]},
            "Department": {"rich_text": [{"text": {"content": department}}]},
            "Task": {"rich_text": [{"text": {"content": task}}]},
            "Status": {"rich_text": [{"text": {"content": status}}]},
            "Date": {"date": {"start": date}},
        },
    }


def deliver_notification(notification: dict) -> dict:
    env = load_virtual_team_env()
    api_key = env.get("NOTION_API_KEY", "")
    database_id = env.get("NOTION_DATABASE_ID", "")
    if not api_key or not database_id:
        return {"status": "skipped", "reason": "missing_notion_credentials"}

    payload = notification["payload"]
    event = payload.get("event", {})
    task = payload.get("task", {})
    agent = payload.get("agent", {})
    now = datetime.now().astimezone().strftime("%Y-%m-%d")
    response = _api_call(
        api_key,
        database_id,
        _page_payload(
            database_id,
            agent=agent.get("name", task.get("agent_id", "")),
            department=agent.get("department_name", ""),
            task=task.get("title", event.get("event_type", "")),
            status=event.get("event_type", ""),
            date=now,
        ),
    )
    return {"status": "sent", "external_id": response.get("id", "")}


def sync_activity_log(mode: str = "today", log_path: str | Path | None = None) -> dict:
    env = load_virtual_team_env()
    api_key = env.get("NOTION_API_KEY", "")
    database_id = env.get("NOTION_DATABASE_ID", "")
    if not api_key or not database_id:
        return {"status": "skipped", "reason": "missing_notion_credentials"}

    path = Path(log_path) if log_path else ACTIVITY_LOG_PATH
    if not path.exists():
        return {"status": "ok", "synced": 0}

    entries = json.loads(path.read_text(encoding="utf-8"))
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    if mode == "today":
        entries = [entry for entry in entries if entry.get("date") == today]

    synced = 0
    for entry in entries:
        _api_call(
            api_key,
            database_id,
            _page_payload(
                database_id,
                agent=entry.get("agent", ""),
                department=entry.get("department", ""),
                task=entry.get("task", ""),
                status=entry.get("status", ""),
                date=entry.get("date", today),
            ),
        )
        synced += 1

    return {"status": "sent", "synced": synced}
