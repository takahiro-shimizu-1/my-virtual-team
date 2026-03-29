from __future__ import annotations

import json
import sys
from pathlib import Path

from control.task_store import expire_stale_claims, get_task
from registry.catalog import get_agent

INTEGRATIONS_ROOT = Path(__file__).resolve().parents[1] / "integrations"
if str(INTEGRATIONS_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRATIONS_ROOT))

import activity_log
import notion
import slack

CHANNELS_BY_EVENT = {
    "task.created": ["activity_log"],
    "task.completed": ["activity_log", "slack", "notion"],
    "task.failed": ["activity_log", "slack", "notion"],
    "task.timeout": ["activity_log", "slack"],
    "approval.requested": ["activity_log", "slack"],
}

HANDLERS = {
    "activity_log": activity_log.deliver_notification,
    "slack": slack.deliver_notification,
    "notion": notion.deliver_notification,
}


def _notification_exists(conn, event_id: int, channel: str) -> bool:
    row = conn.execute(
        "SELECT notification_id FROM notifications WHERE event_id = ? AND channel = ?",
        (event_id, channel),
    ).fetchone()
    return bool(row)


def _build_payload(conn, event_row) -> dict:
    task = get_task(conn, event_row["task_id"])
    agent = get_agent(task["agent_id"]) or {}
    return {
        "event": {
            "event_id": event_row["event_id"],
            "event_type": event_row["event_type"],
            "payload": json.loads(event_row["payload_json"]),
            "created_at": event_row["created_at"],
        },
        "task": task,
        "agent": agent,
    }


def _record_notification(conn, *, event_id: int, task_id: str, channel: str, event_type: str, payload: dict) -> int:
    cursor = conn.execute(
        """
        INSERT INTO notifications (event_id, task_id, channel, event_type, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        """,
        (event_id, task_id, channel, event_type, json.dumps(payload, ensure_ascii=False)),
    )
    return cursor.lastrowid


def _record_delivery(conn, *, notification_id: int, result: dict) -> None:
    conn.execute(
        """
        INSERT INTO notification_deliveries (notification_id, status, delivered_at, error_message, external_id)
        VALUES (?, ?, datetime('now'), ?, ?)
        """,
        (
            notification_id,
            result.get("status", "unknown"),
            result.get("reason", "") or result.get("error", ""),
            result.get("external_id", ""),
        ),
    )


def publish_pending_events(conn, limit: int = 50) -> dict:
    expire_stale_claims(conn)
    event_types = tuple(CHANNELS_BY_EVENT.keys())
    placeholders = ", ".join(["?"] * len(event_types))
    rows = conn.execute(
        f"""
        SELECT event_id, task_id, event_type, payload_json, created_at
        FROM task_events
        WHERE event_type IN ({placeholders})
        ORDER BY event_id
        """,
        event_types,
    ).fetchall()

    published = []
    for row in rows:
        if len(published) >= limit:
            break
        channels = CHANNELS_BY_EVENT.get(row["event_type"], [])
        payload = _build_payload(conn, row)
        for channel in channels:
            if _notification_exists(conn, row["event_id"], channel):
                continue
            notification_id = _record_notification(
                conn,
                event_id=row["event_id"],
                task_id=row["task_id"],
                channel=channel,
                event_type=row["event_type"],
                payload=payload,
            )
            handler = HANDLERS[channel]
            result = handler({"payload": payload})
            _record_delivery(conn, notification_id=notification_id, result=result)
            published.append(
                {
                    "event_id": row["event_id"],
                    "task_id": row["task_id"],
                    "channel": channel,
                    "result": result,
                }
            )
            if len(published) >= limit:
                break

    conn.commit()
    return {"published": published, "count": len(published)}
