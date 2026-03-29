from __future__ import annotations

import json
from datetime import datetime, timezone

from control.task_store import expire_stale_claims


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _refresh_skill_health_snapshots(conn) -> list[dict]:
    rows = conn.execute(
        """
        SELECT skill_id,
               COUNT(*) AS total_runs,
               SUM(CASE WHEN result = 'completed' THEN 1 ELSE 0 END) AS success_count,
               MAX(created_at) AS last_run_at
        FROM skill_runs
        WHERE skill_id != ''
        GROUP BY skill_id
        ORDER BY skill_id
        """
    ).fetchall()

    snapshots = []
    for row in rows:
        total_runs = row["total_runs"]
        success_rate = (row["success_count"] or 0) / total_runs if total_runs else 0.0
        if total_runs < 3:
            health_status = "warming"
        elif success_rate >= 0.8:
            health_status = "healthy"
        elif success_rate >= 0.5:
            health_status = "watch"
        else:
            health_status = "degraded"

        detail = {
            "skill_id": row["skill_id"],
            "total_runs": total_runs,
            "success_rate": round(success_rate, 3),
            "last_run_at": row["last_run_at"],
        }
        conn.execute(
            """
            INSERT INTO skill_health_snapshots (skill_id, health_status, detail_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (row["skill_id"], health_status, json.dumps(detail, ensure_ascii=False), _now_iso()),
        )
        snapshots.append(
            {
                "skill_id": row["skill_id"],
                "health_status": health_status,
                **detail,
            }
        )

    conn.commit()
    return snapshots


def build_health_report(conn, sweep_timeouts: bool = False) -> dict:
    expired = expire_stale_claims(conn) if sweep_timeouts else []

    status_counts = {
        row["status"]: row["count"]
        for row in conn.execute(
            "SELECT status, COUNT(*) AS count FROM tasks GROUP BY status ORDER BY status"
        ).fetchall()
    }
    ready_count = conn.execute(
        """
        SELECT COUNT(*) AS ready_count
        FROM tasks t
        WHERE t.status = 'created'
          AND NOT EXISTS (
            SELECT 1
            FROM task_dependencies td
            JOIN tasks dep ON dep.task_id = td.depends_on_task_id
            WHERE td.task_id = t.task_id AND dep.status != 'completed'
          )
          AND NOT EXISTS (
            SELECT 1 FROM task_approvals ta
            WHERE ta.task_id = t.task_id AND ta.decision = 'pending'
          )
        """
    ).fetchone()["ready_count"]

    stale_locks = conn.execute(
        "SELECT COUNT(*) AS stale_count FROM task_locks WHERE expires_at != '' AND expires_at <= ?",
        (_now_iso(),),
    ).fetchone()["stale_count"]
    lock_count = conn.execute("SELECT COUNT(*) AS lock_count FROM task_locks").fetchone()["lock_count"]

    recent_failures = [
        {
            "task_id": row["task_id"],
            "title": row["title"],
            "status": row["status"],
            "error_message": row["error_message"],
            "updated_at": row["updated_at"],
        }
        for row in conn.execute(
            """
            SELECT task_id, title, status, error_message, updated_at
            FROM tasks
            WHERE status IN ('failed', 'blocked')
            ORDER BY updated_at DESC
            LIMIT 10
            """
        ).fetchall()
    ]

    notifications = {
        row["status"]: row["count"]
        for row in conn.execute(
            """
            SELECT nd.status, COUNT(*) AS count
            FROM notification_deliveries nd
            GROUP BY nd.status
            ORDER BY nd.status
            """
        ).fetchall()
    }

    recent_diffs = [
        {
            "path": row["path"],
            "diff_type": row["diff_type"],
            "created_at": row["created_at"],
        }
        for row in conn.execute(
            """
            SELECT path, diff_type, created_at
            FROM knowledge_diffs
            ORDER BY diff_id DESC
            LIMIT 10
            """
        ).fetchall()
    ]

    snapshots = _refresh_skill_health_snapshots(conn)

    return {
        "status_counts": status_counts,
        "ready_count": ready_count,
        "locks": {
            "active": lock_count,
            "stale": stale_locks,
        },
        "recent_failures": recent_failures,
        "notifications": notifications,
        "knowledge_diffs": recent_diffs,
        "skill_health": snapshots,
        "expired_tasks": expired,
    }

