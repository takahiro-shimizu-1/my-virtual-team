from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from control.task_store import create_task
from registry.catalog import get_agent, get_skill, load_skills_registry


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _knowledge_paths_for_skill(skill_id: str) -> list[str]:
    skill = get_skill(skill_id) or {}
    tracked = set()
    file_path = skill.get("file", "")
    if isinstance(file_path, str) and file_path:
        tracked.add(file_path)
    for path in skill.get("depends_on", []) if isinstance(skill.get("depends_on", []), list) else []:
        if isinstance(path, str) and path:
            tracked.add(path)
    for agent_id in skill.get("agents", []) if isinstance(skill.get("agents", []), list) else []:
        agent = get_agent(agent_id) or {}
        agent_file = agent.get("file", "")
        if isinstance(agent_file, str) and agent_file:
            tracked.add(agent_file)
    return sorted(tracked)


def related_knowledge_diffs(conn, skill_id: str, *, recent_days: int = 7) -> list[dict]:
    paths = _knowledge_paths_for_skill(skill_id)
    if not paths:
        return []
    cutoff = (_utc_now() - timedelta(days=recent_days)).isoformat(timespec="seconds")
    placeholders = ",".join("?" for _ in paths)
    rows = conn.execute(
        f"""
        SELECT diff_id, path, diff_type, detail_json, created_at
        FROM knowledge_diffs
        WHERE path IN ({placeholders}) AND created_at >= ?
        ORDER BY diff_id DESC
        """,
        (*paths, cutoff),
    ).fetchall()
    return [
        {
            "diff_id": row["diff_id"],
            "path": row["path"],
            "diff_type": row["diff_type"],
            "detail_json": row["detail_json"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _windowed_average(runs: list[dict], *, start: datetime, end: datetime) -> float | None:
    window = [
        run["score"]
        for run in runs
        if start <= _parse_ts(run["created_at"]) < end
    ]
    if not window:
        return None
    return sum(window) / len(window)


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
        prior_window_end = cutoff
        prior_window_start = cutoff - timedelta(days=recent_days)
        baseline_avg = _windowed_average(runs, start=prior_window_start, end=prior_window_end)
        drift_drop = round((baseline_avg - recent_avg), 3) if baseline_avg is not None else 0.0

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
        if baseline_avg is not None and drift_drop > 0.15:
            reasons.append("week_over_week_drift")

        knowledge_changes = related_knowledge_diffs(conn, skill_id, recent_days=recent_days)

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
                "baseline_avg": round(baseline_avg, 3) if baseline_avg is not None else None,
                "drift_drop": drift_drop,
                "trend": trend,
                "consecutive_failures": consecutive_failures,
                "flagged": flagged,
                "reasons": reasons,
                "health_status": health_status,
                "last_run_at": runs[-1]["created_at"],
                "related_changes": knowledge_changes,
            }
        )
    return report


def _owner_for_skill(skill_id: str) -> str:
    if skill_id.startswith("agent:"):
        return skill_id.split(":", 1)[1]
    skill = get_skill(skill_id) or {}
    agents = skill.get("agents", []) if isinstance(skill.get("agents", []), list) else []
    return agents[0] if agents else ""


def enqueue_knowledge_review_tasks(
    conn,
    *,
    recent_days: int = 7,
    created_by: str = "system",
    source: str = "knowledge-watcher",
    dry_run: bool = False,
) -> dict:
    created = []

    for skill in load_skills_registry():
        skill_id = skill.get("name", "")
        if not skill_id:
            continue
        changes = related_knowledge_diffs(conn, skill_id, recent_days=recent_days)
        if not changes:
            continue

        latest_diff_id = changes[0]["diff_id"]
        idempotency_key = f"knowledge-watch:{skill_id}:{latest_diff_id}"
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
            created.append({"status": "skipped", "skill_id": skill_id, "task_id": existing["task_id"]})
            continue

        affected_files = sorted({change["path"] for change in changes})
        payload = {
            "skill_id": skill_id,
            "knowledge_changes": changes,
            "verification_scope": "context-refresh",
        }
        if dry_run:
            created.append({"status": "dry_run", "skill_id": skill_id, "payload": payload})
            continue

        task = create_task(
            conn,
            title=f"Revalidate skill context: {skill_id}",
            description=f"{len(changes)} recent knowledge change(s) touched this skill context.",
            agent_id=_owner_for_skill(skill_id),
            priority="normal",
            task_mode="tracked_fast_path",
            created_by=created_by,
            payload=payload,
            source=source,
            idempotency_key=idempotency_key,
            affected_files=affected_files,
            affected_skills=[skill_id],
            lock_targets=[f"skill:{skill_id}"],
        )
        created.append({"status": "created", "skill_id": skill_id, "task_id": task["task_id"]})

    return {
        "status": "ok",
        "tasks": created,
        "triggered_skills": len([item for item in created if item["status"] in {"created", "dry_run"}]),
    }


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
            "knowledge_changes": snapshot["related_changes"],
        }
        if dry_run:
            created.append({"status": "dry_run", "skill_id": snapshot["skill_id"], "payload": task_payload})
            continue

        task = create_task(
            conn,
            title=f"Improve skill: {snapshot['skill_id']}",
            description=(
                f"Skill health is {snapshot['health_status']} "
                f"(trend={snapshot['trend']}, avg={snapshot['avg_score']}, recent={snapshot['recent_avg']})"
            ),
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
