from __future__ import annotations

from control.skill_monitor import enqueue_improvement_tasks, enqueue_knowledge_review_tasks
from events.bus import publish_pending_events
from health.aggregate import build_health_report
from watchers.local_files import scan_local_assets


def run_maintenance(
    conn,
    *,
    recent_days: int = 7,
    roots: list[str] | None = None,
    created_by: str = "system",
    dry_run: bool = False,
    event_limit: int = 100,
) -> dict:
    watch_result = scan_local_assets(conn, roots=roots)
    knowledge_result = enqueue_knowledge_review_tasks(
        conn,
        recent_days=recent_days,
        created_by=created_by,
        dry_run=dry_run,
    )
    improvement_result = enqueue_improvement_tasks(
        conn,
        recent_days=recent_days,
        created_by=created_by,
        dry_run=dry_run,
    )
    event_result = publish_pending_events(conn, limit=event_limit)
    health_report = build_health_report(conn)
    return {
        "status": "ok",
        "watch": watch_result,
        "knowledge_review": knowledge_result,
        "self_improve": improvement_result,
        "events": event_result,
        "health": health_report,
    }
