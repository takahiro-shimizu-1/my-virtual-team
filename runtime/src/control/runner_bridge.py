from __future__ import annotations

import uuid

from control.decomposer import decompose_request
from control.task_store import claim_task, create_task, dispatch_ready_tasks


def _workflow_id() -> str:
    return f"wf-{uuid.uuid4().hex[:12]}"


def plan_request(
    conn,
    *,
    prompt: str,
    command: str | None = None,
    created_by: str = "chief",
    source: str = "chief",
    dispatch: bool = False,
) -> dict:
    plan = decompose_request(prompt, command)
    workflow_id = _workflow_id()
    task_ids_by_index: dict[int, str] = {}
    created_tasks = []

    for index, spec in enumerate(plan["tasks"]):
        depends_on = [task_ids_by_index[i] for i in spec["depends_on_indexes"]]
        task = create_task(
            conn,
            title=spec["title"],
            description=spec["description"],
            agent_id=spec["agent_id"],
            priority="normal",
            task_mode=spec["task_mode"],
            created_by=created_by,
            payload=spec["payload"],
            depends_on=depends_on,
            parent_task_id="",
            max_attempts=2 if spec["payload"].get("review_mode") else 1,
            source=source,
            workflow_id=workflow_id,
            idempotency_key=f"{workflow_id}:{index}",
            affected_files=[],
            affected_skills=spec["affected_skills"],
            approval_required=spec["approval_required"],
            approval_note=spec["approval_note"],
            approval_requested_by=created_by,
        )
        created_tasks.append(task)
        task_ids_by_index[index] = task["task_id"]

    dispatched_tasks = dispatch_ready_tasks(conn) if dispatch else []
    return {
        "workflow_id": workflow_id,
        "route": plan["route"],
        "workflow_name": plan["workflow_name"],
        "created_tasks": created_tasks,
        "dispatched_tasks": dispatched_tasks,
    }


def start_fast_path(
    conn,
    *,
    prompt: str,
    command: str | None = None,
    created_by: str = "chief",
    source: str = "chief",
    runner_id: str = "chief",
    lease_seconds: int = 300,
    claim_immediately: bool = True,
) -> dict:
    planned = plan_request(
        conn,
        prompt=prompt,
        command=command,
        created_by=created_by,
        source=source,
        dispatch=True,
    )

    if len(planned["created_tasks"]) != 1:
        raise RuntimeError("fast path can only start a single task workflow")

    task = planned["created_tasks"][0]
    if any(approval["decision"] == "pending" for approval in task.get("approvals", [])):
        return {
            **planned,
            "status": "approval_required",
            "claimed_task": None,
        }

    if not claim_immediately:
        return {
            **planned,
            "status": "dispatched",
            "claimed_task": None,
        }

    claimed_task = claim_task(conn, task["task_id"], runner_id, lease_seconds)
    return {
        **planned,
        "status": "claimed",
        "claimed_task": claimed_task,
    }
