from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from exports.jsonl import append_event_mirror


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_json(value: str) -> dict | list:
    if not value:
        return {}
    return json.loads(value)


def serialize(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def row_to_task(row) -> dict:
    return {
        "task_id": row["task_id"],
        "title": row["title"],
        "description": row["description"],
        "agent_id": row["agent_id"],
        "source": row["source"] if "source" in row.keys() else "manual",
        "workflow_id": row["workflow_id"] if "workflow_id" in row.keys() else "",
        "idempotency_key": row["idempotency_key"] if "idempotency_key" in row.keys() else "",
        "status": row["status"],
        "priority": row["priority"],
        "task_mode": row["task_mode"],
        "created_by": row["created_by"],
        "claimed_by": row["claimed_by"],
        "payload": parse_json(row["payload_json"]),
        "lock_targets": parse_json(row["lock_targets_json"]),
        "affected_files": parse_json(row["affected_files_json"]) if "affected_files_json" in row.keys() else [],
        "affected_skills": parse_json(row["affected_skills_json"]) if "affected_skills_json" in row.keys() else [],
        "parent_task_id": row["parent_task_id"],
        "max_attempts": row["max_attempts"],
        "current_attempt": row["current_attempt"],
        "lease_expires_at": row["lease_expires_at"],
        "last_heartbeat_at": row["last_heartbeat_at"],
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "claimed_at": row["claimed_at"],
        "completed_at": row["completed_at"],
    }


def cleanup_expired_locks(conn) -> int:
    now = now_iso()
    cursor = conn.execute("DELETE FROM task_locks WHERE expires_at != '' AND expires_at <= ?", (now,))
    return cursor.rowcount


def has_pending_approval(conn, task_id: str) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*) AS pending_count
        FROM task_approvals
        WHERE task_id = ? AND decision = 'pending'
        """,
        (task_id,),
    ).fetchone()
    return bool(row["pending_count"])


def has_incomplete_dependencies(conn, task_id: str) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*) AS pending_count
        FROM task_dependencies td
        JOIN tasks t ON t.task_id = td.depends_on_task_id
        WHERE td.task_id = ? AND t.status != 'completed'
        """,
        (task_id,),
    ).fetchone()
    return bool(row["pending_count"])


def record_event(conn, task_id: str, event_type: str, payload: dict) -> dict:
    created_at = now_iso()
    cursor = conn.execute(
        "INSERT INTO task_events (task_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?)",
        (task_id, event_type, serialize(payload), created_at),
    )
    event = {
        "event_id": cursor.lastrowid,
        "task_id": task_id,
        "event_type": event_type,
        "payload": payload,
        "created_at": created_at,
    }
    append_event_mirror(event)
    return event


def record_skill_run(conn, task: dict, result: str, score: float) -> None:
    payload = task.get("payload", {})
    skill_id = payload.get("skill_id") or (f"agent:{task['agent_id']}" if task.get("agent_id") else "")
    if not skill_id:
        return
    conn.execute(
        """
        INSERT INTO skill_runs (task_id, agent_id, skill_id, result, score, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (task["task_id"], task["agent_id"], skill_id, result, score, now_iso()),
    )


def acquire_locks(conn, task_id: str, lock_targets: list[str], expires_at: str) -> list[str]:
    acquired_at = now_iso()
    held = []
    for lock_key in lock_targets:
        existing = conn.execute(
            "SELECT task_id, expires_at FROM task_locks WHERE lock_key = ?",
            (lock_key,),
        ).fetchone()
        if existing and existing["expires_at"] > acquired_at and existing["task_id"] != task_id:
            raise RuntimeError(f"lock already held: {lock_key}")
        if existing:
            conn.execute("DELETE FROM task_locks WHERE lock_key = ?", (lock_key,))
        conn.execute(
            "INSERT INTO task_locks (lock_key, task_id, acquired_at, expires_at) VALUES (?, ?, ?, ?)",
            (lock_key, task_id, acquired_at, expires_at),
        )
        held.append(lock_key)
    return held


def release_locks(conn, task_id: str) -> int:
    cursor = conn.execute("DELETE FROM task_locks WHERE task_id = ?", (task_id,))
    return cursor.rowcount


def create_task(
    conn,
    *,
    title: str,
    description: str = "",
    agent_id: str = "",
    priority: str = "normal",
    task_mode: str = "tracked_fast_path",
    created_by: str = "human",
    payload: dict | None = None,
    lock_targets: list[str] | None = None,
    depends_on: list[str] | None = None,
    parent_task_id: str = "",
    max_attempts: int = 1,
    source: str = "manual",
    workflow_id: str = "",
    idempotency_key: str = "",
    affected_files: list[str] | None = None,
    affected_skills: list[str] | None = None,
    approval_required: bool = False,
    approval_note: str = "",
    approval_requested_by: str = "",
    task_id: str | None = None,
) -> dict:
    payload = payload or {}
    lock_targets = lock_targets or []
    depends_on = depends_on or []
    affected_files = affected_files or []
    affected_skills = affected_skills or []
    task_id = task_id or f"task-{uuid.uuid4().hex[:12]}"
    timestamp = now_iso()

    conn.execute(
        """
        INSERT INTO tasks (
          task_id, title, description, agent_id, status, priority, task_mode, created_by,
          payload_json, lock_targets_json, parent_task_id, max_attempts, current_attempt,
          source, workflow_id, idempotency_key, affected_files_json, affected_skills_json,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'created', ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            title,
            description,
            agent_id,
            priority,
            task_mode,
            created_by,
            serialize(payload),
            serialize(lock_targets),
            parent_task_id,
            max_attempts,
            source,
            workflow_id,
            idempotency_key,
            serialize(affected_files),
            serialize(affected_skills),
            timestamp,
            timestamp,
        ),
    )

    for dependency in depends_on:
        conn.execute(
            "INSERT INTO task_dependencies (task_id, depends_on_task_id, created_at) VALUES (?, ?, ?)",
            (task_id, dependency, timestamp),
        )

    record_event(
        conn,
        task_id,
        "task.created",
        {
            "title": title,
            "agent_id": agent_id,
            "priority": priority,
            "task_mode": task_mode,
            "depends_on": depends_on,
            "lock_targets": lock_targets,
            "workflow_id": workflow_id,
            "source": source,
            "affected_skills": affected_skills,
        },
    )
    if approval_required:
        conn.execute(
            """
            INSERT INTO task_approvals (task_id, requested_by, decision, note, created_at)
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (task_id, approval_requested_by or created_by, approval_note, timestamp),
        )
        record_event(
            conn,
            task_id,
            "approval.requested",
            {
                "requested_by": approval_requested_by or created_by,
                "note": approval_note,
            },
        )
    conn.commit()
    return get_task(conn, task_id)


def get_task(conn, task_id: str) -> dict:
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if not row:
        raise RuntimeError(f"task not found: {task_id}")
    task = row_to_task(row)
    task["dependencies"] = [
        dep["depends_on_task_id"]
        for dep in conn.execute(
            "SELECT depends_on_task_id FROM task_dependencies WHERE task_id = ? ORDER BY depends_on_task_id",
            (task_id,),
        ).fetchall()
    ]
    task["outputs"] = [
        {"path": output["path"], "kind": output["kind"]}
        for output in conn.execute(
            "SELECT path, kind FROM task_outputs WHERE task_id = ? ORDER BY output_id",
            (task_id,),
        ).fetchall()
    ]
    task["approvals"] = [
        {
            "approval_id": approval["approval_id"],
            "requested_by": approval["requested_by"],
            "decision": approval["decision"],
            "note": approval["note"],
            "created_at": approval["created_at"],
            "resolved_at": approval["resolved_at"],
        }
        for approval in conn.execute(
            """
            SELECT approval_id, requested_by, decision, note, created_at, resolved_at
            FROM task_approvals
            WHERE task_id = ?
            ORDER BY approval_id
            """,
            (task_id,),
        ).fetchall()
    ]
    return task


def dispatch_ready_tasks(conn, limit: int = 20) -> list[dict]:
    expire_stale_claims(conn)
    cleanup_expired_locks(conn)
    rows = conn.execute(
        """
        SELECT t.task_id
        FROM tasks t
        WHERE t.status = 'created'
          AND NOT EXISTS (
            SELECT 1
            FROM task_dependencies td
            JOIN tasks dep ON dep.task_id = td.depends_on_task_id
            WHERE td.task_id = t.task_id AND dep.status != 'completed'
          )
          AND NOT EXISTS (
            SELECT 1
            FROM task_approvals ta
            WHERE ta.task_id = t.task_id AND ta.decision = 'pending'
          )
        ORDER BY t.created_at
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    dispatched = []
    for row in rows:
        task_id = row["task_id"]
        conn.execute(
            "UPDATE tasks SET status = 'dispatched', updated_at = ? WHERE task_id = ?",
            (now_iso(), task_id),
        )
        record_event(conn, task_id, "task.dispatched", {})
        dispatched.append(get_task(conn, task_id))

    conn.commit()
    return dispatched


def claim_task(conn, task_id: str, runner_id: str, lease_seconds: int = 300) -> dict:
    expire_stale_claims(conn)
    cleanup_expired_locks(conn)
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if not row:
        raise RuntimeError(f"task not found: {task_id}")
    task = row_to_task(row)

    if task["status"] not in {"created", "dispatched"}:
        raise RuntimeError(f"task is not claimable: {task['status']}")
    if has_incomplete_dependencies(conn, task_id):
        raise RuntimeError("task has incomplete dependencies")
    if has_pending_approval(conn, task_id):
        raise RuntimeError("task has pending approval")
    if task["current_attempt"] >= task["max_attempts"]:
        raise RuntimeError("task has exhausted max attempts")

    timestamp = now_iso()
    lease_expires_at = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat(timespec="seconds")
    attempt_no = task["current_attempt"] + 1
    acquire_locks(conn, task_id, task["lock_targets"], lease_expires_at)

    conn.execute(
        """
        UPDATE tasks
        SET status = 'claimed',
            claimed_by = ?,
            claimed_at = ?,
            last_heartbeat_at = ?,
            lease_expires_at = ?,
            current_attempt = ?,
            updated_at = ?,
            error_message = ''
        WHERE task_id = ?
        """,
        (runner_id, timestamp, timestamp, lease_expires_at, attempt_no, timestamp, task_id),
    )
    conn.execute(
        """
        INSERT INTO task_attempts (task_id, attempt_no, runner_id, status, started_at)
        VALUES (?, ?, ?, 'running', ?)
        """,
        (task_id, attempt_no, runner_id, timestamp),
    )
    record_event(
        conn,
        task_id,
        "task.claimed",
        {"runner_id": runner_id, "lease_seconds": lease_seconds, "attempt_no": attempt_no},
    )
    conn.commit()
    return get_task(conn, task_id)


def heartbeat_task(conn, task_id: str, lease_seconds: int = 300) -> dict:
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if not row:
        raise RuntimeError(f"task not found: {task_id}")
    task = row_to_task(row)
    if task["status"] != "claimed":
        raise RuntimeError(f"task is not running: {task['status']}")

    timestamp = now_iso()
    lease_expires_at = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat(timespec="seconds")
    conn.execute(
        """
        UPDATE tasks
        SET last_heartbeat_at = ?, lease_expires_at = ?, updated_at = ?
        WHERE task_id = ?
        """,
        (timestamp, lease_expires_at, timestamp, task_id),
    )
    conn.execute(
        "UPDATE task_locks SET expires_at = ? WHERE task_id = ?",
        (lease_expires_at, task_id),
    )
    record_event(conn, task_id, "task.heartbeat", {"lease_seconds": lease_seconds})
    conn.commit()
    return get_task(conn, task_id)


def resolve_task_approval(conn, task_id: str, decision: str, note: str = "", resolved_by: str = "chief") -> dict:
    approval = conn.execute(
        """
        SELECT approval_id
        FROM task_approvals
        WHERE task_id = ? AND decision = 'pending'
        ORDER BY approval_id DESC
        LIMIT 1
        """,
        (task_id,),
    ).fetchone()
    if not approval:
        raise RuntimeError(f"pending approval not found for task: {task_id}")

    timestamp = now_iso()
    merged_note = note if note else resolved_by
    conn.execute(
        """
        UPDATE task_approvals
        SET decision = ?, note = ?, resolved_at = ?
        WHERE approval_id = ?
        """,
        (decision, merged_note, timestamp, approval["approval_id"]),
    )

    if decision == "rejected":
        conn.execute(
            """
            UPDATE tasks
            SET status = 'blocked',
                error_message = ?,
                updated_at = ?
            WHERE task_id = ?
            """,
            (merged_note, timestamp, task_id),
        )
        record_event(conn, task_id, "approval.rejected", {"resolved_by": resolved_by, "note": merged_note})
    else:
        record_event(conn, task_id, "approval.approved", {"resolved_by": resolved_by, "note": merged_note})

    conn.commit()
    return get_task(conn, task_id)


def complete_task(conn, task_id: str, outputs: list[str] | None = None) -> dict:
    outputs = outputs or []
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if not row:
        raise RuntimeError(f"task not found: {task_id}")
    task = row_to_task(row)
    if task["status"] != "claimed":
        raise RuntimeError(f"task is not completable: {task['status']}")

    timestamp = now_iso()
    conn.execute(
        """
        UPDATE tasks
        SET status = 'completed',
            completed_at = ?,
            updated_at = ?,
            lease_expires_at = ''
        WHERE task_id = ?
        """,
        (timestamp, timestamp, task_id),
    )
    conn.execute(
        """
        UPDATE task_attempts
        SET status = 'completed', finished_at = ?
        WHERE task_id = ? AND attempt_no = ?
        """,
        (timestamp, task_id, task["current_attempt"]),
    )

    for output_path in outputs:
        conn.execute(
            "INSERT INTO task_outputs (task_id, path, kind, created_at) VALUES (?, ?, 'artifact', ?)",
            (task_id, output_path, timestamp),
        )

    released = release_locks(conn, task_id)
    record_skill_run(conn, task, "completed", 1.0)
    record_event(conn, task_id, "task.completed", {"outputs": outputs, "released_locks": released})
    conn.commit()
    return get_task(conn, task_id)


def cancel_task(conn, task_id: str, reason: str = "", cancelled_by: str = "system") -> dict:
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if not row:
        raise RuntimeError(f"task not found: {task_id}")
    task = row_to_task(row)
    if task["status"] in {"completed", "failed", "cancelled"}:
        raise RuntimeError(f"task is not cancellable: {task['status']}")

    timestamp = now_iso()
    note = reason or f"cancelled by {cancelled_by}"
    released = release_locks(conn, task_id)

    if task["status"] == "claimed" and task["current_attempt"] > 0:
        conn.execute(
            """
            UPDATE task_attempts
            SET status = 'cancelled', error_message = ?, finished_at = ?
            WHERE task_id = ? AND attempt_no = ?
            """,
            (note, timestamp, task_id, task["current_attempt"]),
        )

    conn.execute(
        """
        UPDATE tasks
        SET status = 'cancelled',
            updated_at = ?,
            lease_expires_at = '',
            last_heartbeat_at = '',
            claimed_by = CASE WHEN status = 'claimed' THEN claimed_by ELSE '' END,
            error_message = ?
        WHERE task_id = ?
        """,
        (timestamp, note, task_id),
    )
    record_event(
        conn,
        task_id,
        "task.cancelled",
        {"cancelled_by": cancelled_by, "reason": note, "released_locks": released},
    )
    conn.commit()
    return get_task(conn, task_id)


def fail_task(conn, task_id: str, error_message: str, retryable: bool = False) -> dict:
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if not row:
        raise RuntimeError(f"task not found: {task_id}")
    task = row_to_task(row)
    if task["status"] != "claimed":
        raise RuntimeError(f"task is not fail-able: {task['status']}")

    timestamp = now_iso()
    released = release_locks(conn, task_id)
    conn.execute(
        """
        UPDATE task_attempts
        SET status = 'failed', error_message = ?, finished_at = ?
        WHERE task_id = ? AND attempt_no = ?
        """,
        (error_message, timestamp, task_id, task["current_attempt"]),
    )

    if retryable and task["current_attempt"] < task["max_attempts"]:
        conn.execute(
            """
            UPDATE tasks
            SET status = 'created',
                updated_at = ?,
                lease_expires_at = '',
                last_heartbeat_at = '',
                claimed_by = '',
                claimed_at = '',
                error_message = ?
            WHERE task_id = ?
            """,
            (timestamp, error_message, task_id),
        )
        record_event(
            conn,
            task_id,
            "task.requeued",
            {"error_message": error_message, "released_locks": released},
        )
    else:
        conn.execute(
            """
            UPDATE tasks
            SET status = 'failed',
                updated_at = ?,
                lease_expires_at = '',
                error_message = ?
            WHERE task_id = ?
            """,
            (timestamp, error_message, task_id),
        )
        record_event(
            conn,
            task_id,
            "task.failed",
            {"error_message": error_message, "released_locks": released},
        )

    record_skill_run(conn, task, "failed", 0.0)
    conn.commit()
    return get_task(conn, task_id)


def expire_stale_claims(conn) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM tasks
        WHERE status = 'claimed'
          AND lease_expires_at != ''
          AND lease_expires_at <= ?
        ORDER BY lease_expires_at
        """,
        (now_iso(),),
    ).fetchall()
    expired = []
    for row in rows:
        task = row_to_task(row)
        timestamp = now_iso()
        released = release_locks(conn, task["task_id"])
        conn.execute(
            """
            UPDATE task_attempts
            SET status = 'failed', error_message = ?, finished_at = ?
            WHERE task_id = ? AND attempt_no = ?
            """,
            ("lease expired", timestamp, task["task_id"], task["current_attempt"]),
        )
        if task["current_attempt"] < task["max_attempts"]:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'created',
                    updated_at = ?,
                    lease_expires_at = '',
                    last_heartbeat_at = '',
                    claimed_by = '',
                    claimed_at = '',
                    error_message = 'lease expired'
                WHERE task_id = ?
                """,
                (timestamp, task["task_id"]),
            )
            record_event(
                conn,
                task["task_id"],
                "task.timeout",
                {"released_locks": released, "requeued": True},
            )
            record_event(
                conn,
                task["task_id"],
                "task.requeued",
                {"error_message": "lease expired", "released_locks": released},
            )
            record_skill_run(conn, task, "timeout", 0.0)
        else:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'failed',
                    updated_at = ?,
                    lease_expires_at = '',
                    error_message = 'lease expired'
                WHERE task_id = ?
                """,
                (timestamp, task["task_id"]),
            )
            record_event(
                conn,
                task["task_id"],
                "task.timeout",
                {"released_locks": released, "requeued": False},
            )
            record_skill_run(conn, task, "timeout", 0.0)
        expired.append(get_task(conn, task["task_id"]))

    conn.commit()
    return expired
