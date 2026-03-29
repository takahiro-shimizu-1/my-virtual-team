from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from control.task_store import create_task
from registry.catalog import get_skill


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def analyze_skill_health(conn, recent_days: int = 7) -> list[dict]:
    cutoff = _utc_now() - timedelta(days=recent_days)
    rows = conn.execute(
        """
        SELECT skill_id, result, score, created_at
        FROM skill_runs
        WHERE skill_id != ''
        ORDER BY skill_id, created_at
        """
    ).fetchall()

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["skill_id"]].append(
            {
                "result": row["result"],
                "score": float(row["score"] or 0.0),
                "created_at": row["created_at"],
            }
        )

    report = []
    for skill_id, runs in sorted(grouped.items()):
        total_runs = len(runs)
        avg_score = sum(run["score"] for run in runs) / total_runs if total_runs else 0.0
        recent_runs = [run for run in runs if _parse_ts(run["created_at"]) >= cutoff]
        recent_avg = sum(run["score"] for run in recent_runs) / len(recent_runs) if recent_runs else avg_score

        consecutive_failures = 0
        for run in reversed(runs):
            if run["result"] in {"failed", "fail"}:
                consecutive_failures += 1
            else:
                break

        if consecutive_failures >= 3:
            trend = "broken"
        else:
            delta = recent_avg - avg_score
            if delta > 0.05:
                trend = "improving"
            elif delta < -0.05:
                trend = "declining"
            else:
                trend = "stable"

        reasons = []
        if avg_score < 0.7:
            reasons.append("low_avg_score")
        if trend == "declining":
            reasons.append("declining")
        if trend == "broken":
            reasons.append("broken")

        flagged = bool(reasons)
        if total_runs < 3:
            health_status = "warming"
        elif trend == "broken":
            health_status = "broken"
        elif avg_score >= 0.8 and trend in {"stable", "improving"}:
            health_status = "healthy"
        elif flagged:
            health_status = "degraded"
        else:
            health_status = "watch"

        report.append(
            {
                "skill_id": skill_id,
                "total_runs": total_runs,
                "avg_score": round(avg_score, 3),
                "recent_avg": round(recent_avg, 3),
                "trend": trend,
                "consecutive_failures": consecutive_failures,
                "flagged": flagged,
                "reasons": reasons,
                "health_status": health_status,
                "last_run_at": runs[-1]["created_at"],
            }
        )
    return report


def _owner_for_skill(skill_id: str) -> str:
    if skill_id.startswith("agent:"):
        return skill_id.split(":", 1)[1]
    skill = get_skill(skill_id) or {}
    agents = skill.get("agents", []) if isinstance(skill.get("agents", []), list) else []
    return agents[0] if agents else ""


def enqueue_improvement_tasks(
    conn,
    *,
    recent_days: int = 7,
    created_by: str = "system",
    source: str = "self-improve",
    dry_run: bool = False,
) -> dict:
    snapshots = analyze_skill_health(conn, recent_days=recent_days)
    created = []

    for snapshot in snapshots:
        if not snapshot["flagged"]:
            continue

        idempotency_key = f"self-improve:{snapshot['skill_id']}:{snapshot['trend']}"
        existing = conn.execute(
            """
            SELECT task_id
            FROM tasks
            WHERE idempotency_key = ?
              AND status NOT IN ('completed', 'failed', 'blocked')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (idempotency_key,),
        ).fetchone()
        if existing:
            created.append({"status": "skipped", "skill_id": snapshot["skill_id"], "task_id": existing["task_id"]})
            continue

        task_payload = {
            "skill_id": snapshot["skill_id"],
            "improvement_reason": snapshot["reasons"][0] if snapshot["reasons"] else snapshot["trend"],
            "health_snapshot": snapshot,
        }
        if dry_run:
            created.append({"status": "dry_run", "skill_id": snapshot["skill_id"], "payload": task_payload})
            continue

        task = create_task(
            conn,
            title=f"Improve skill: {snapshot['skill_id']}",
            description=f"Skill health is {snapshot['health_status']} (trend={snapshot['trend']}, avg={snapshot['avg_score']}, recent={snapshot['recent_avg']})",
            agent_id=_owner_for_skill(snapshot["skill_id"]),
            priority="high" if snapshot["trend"] == "broken" else "normal",
            task_mode="tracked_fast_path",
            created_by=created_by,
            payload=task_payload,
            source=source,
            idempotency_key=idempotency_key,
            affected_skills=[snapshot["skill_id"]],
            lock_targets=[f"skill:{snapshot['skill_id']}"],
        )
        created.append({"status": "created", "skill_id": snapshot["skill_id"], "task_id": task["task_id"]})

    return {
        "status": "ok",
        "analyzed": len(snapshots),
        "flagged": len([snapshot for snapshot in snapshots if snapshot["flagged"]]),
        "tasks": created,
    }
