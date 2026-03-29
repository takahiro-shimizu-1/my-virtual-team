from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from control.task_store import (
    cancel_task,
    claim_task,
    complete_task,
    create_task,
    dispatch_ready_tasks,
    expire_stale_claims,
    fail_task,
    get_task,
    heartbeat_task,
    resolve_task_approval,
)
from control.ai_runner import preview_ai_task, run_ai_task
from control.codex_runner import preview_codex_task, run_codex_task
from control.router import route_request
from control.runner_bridge import plan_request, start_fast_path
from db.connection import connect_db
from db.migrate import apply_migrations


def json_arg(raw: str | None) -> dict:
    if not raw:
        return {}
    return json.loads(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Durable task lifecycle CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--task-id")
    create.add_argument("--title", required=True)
    create.add_argument("--description", default="")
    create.add_argument("--agent-id", default="")
    create.add_argument("--priority", default="normal")
    create.add_argument("--mode", default="tracked_fast_path")
    create.add_argument("--created-by", default="human")
    create.add_argument("--payload")
    create.add_argument("--lock-target", action="append", default=[])
    create.add_argument("--depends-on", action="append", default=[])
    create.add_argument("--parent-task-id", default="")
    create.add_argument("--max-attempts", type=int, default=1)
    create.add_argument("--source", default="manual")
    create.add_argument("--workflow-id", default="")
    create.add_argument("--idempotency-key", default="")
    create.add_argument("--affected-file", action="append", default=[])
    create.add_argument("--affected-skill", action="append", default=[])
    create.add_argument("--require-approval", action="store_true")
    create.add_argument("--approval-note", default="")

    claim = subparsers.add_parser("claim")
    claim.add_argument("--task-id", required=True)
    claim.add_argument("--runner", required=True)
    claim.add_argument("--lease-seconds", type=int, default=300)

    heartbeat = subparsers.add_parser("heartbeat")
    heartbeat.add_argument("--task-id", required=True)
    heartbeat.add_argument("--lease-seconds", type=int, default=300)

    complete = subparsers.add_parser("complete")
    complete.add_argument("--task-id", required=True)
    complete.add_argument("--output", action="append", default=[])

    cancel = subparsers.add_parser("cancel")
    cancel.add_argument("--task-id", required=True)
    cancel.add_argument("--reason", default="")
    cancel.add_argument("--cancelled-by", default="system")

    fail = subparsers.add_parser("fail")
    fail.add_argument("--task-id", required=True)
    fail.add_argument("--error", required=True)
    fail.add_argument("--retryable", action="store_true")

    dispatch = subparsers.add_parser("dispatch")
    dispatch.add_argument("--limit", type=int, default=20)

    show = subparsers.add_parser("show")
    show.add_argument("--task-id", required=True)

    approve = subparsers.add_parser("approve")
    approve.add_argument("--task-id", required=True)
    approve.add_argument("--decision", choices=["approved", "rejected"], required=True)
    approve.add_argument("--note", default="")
    approve.add_argument("--resolved-by", default="chief")

    route = subparsers.add_parser("route")
    route.add_argument("--prompt", required=True)
    route.add_argument("--command", dest="department_command", default="")
    route.add_argument("--top-n", type=int, default=3)

    plan = subparsers.add_parser("plan")
    plan.add_argument("--prompt", required=True)
    plan.add_argument("--command", dest="department_command", default="")
    plan.add_argument("--created-by", default="chief")
    plan.add_argument("--source", default="chief")
    plan.add_argument("--dispatch", action="store_true")

    start = subparsers.add_parser("start")
    start.add_argument("--prompt", required=True)
    start.add_argument("--command", dest="department_command", default="")
    start.add_argument("--created-by", default="chief")
    start.add_argument("--source", default="chief")
    start.add_argument("--runner", default="chief")
    start.add_argument("--lease-seconds", type=int, default=300)

    ai = subparsers.add_parser("ai")
    ai_target = ai.add_mutually_exclusive_group(required=True)
    ai_target.add_argument("--task-id")
    ai_target.add_argument("--prompt")
    ai.add_argument("--provider", choices=["auto", "claude", "codex", "gemini"], default="auto")
    ai.add_argument("--command", dest="department_command", default="")
    ai.add_argument("--created-by", default="chief")
    ai.add_argument("--source", default="chief")
    ai.add_argument("--runner", default="local-ai")
    ai.add_argument("--lease-seconds", type=int, default=1800)
    ai.add_argument("--model", default="")
    ai.add_argument("--timeout-seconds", type=int, default=1200)
    ai.add_argument("--target-path", action="append", default=[])
    ai.add_argument("--dry-run", action="store_true")

    codex = subparsers.add_parser("codex")
    codex_target = codex.add_mutually_exclusive_group(required=True)
    codex_target.add_argument("--task-id")
    codex_target.add_argument("--prompt")
    codex.add_argument("--command", dest="department_command", default="")
    codex.add_argument("--created-by", default="chief")
    codex.add_argument("--source", default="chief")
    codex.add_argument("--runner", default="codex")
    codex.add_argument("--lease-seconds", type=int, default=1800)
    codex.add_argument("--model", default="")
    codex.add_argument("--timeout-seconds", type=int, default=1200)
    codex.add_argument("--target-path", action="append", default=[])
    codex.add_argument("--dry-run", action="store_true")

    sweep = subparsers.add_parser("sweep")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    conn = connect_db()
    apply_migrations(conn)

    if args.command == "create":
        result = create_task(
            conn,
            task_id=args.task_id,
            title=args.title,
            description=args.description,
            agent_id=args.agent_id,
            priority=args.priority,
            task_mode=args.mode,
            created_by=args.created_by,
            payload=json_arg(args.payload),
            lock_targets=args.lock_target,
            depends_on=args.depends_on,
            parent_task_id=args.parent_task_id,
            max_attempts=args.max_attempts,
            source=args.source,
            workflow_id=args.workflow_id,
            idempotency_key=args.idempotency_key,
            affected_files=args.affected_file,
            affected_skills=args.affected_skill,
            approval_required=args.require_approval,
            approval_note=args.approval_note,
            approval_requested_by=args.created_by,
        )
    elif args.command == "claim":
        result = claim_task(conn, args.task_id, args.runner, args.lease_seconds)
    elif args.command == "heartbeat":
        result = heartbeat_task(conn, args.task_id, args.lease_seconds)
    elif args.command == "complete":
        result = complete_task(conn, args.task_id, args.output)
    elif args.command == "cancel":
        result = cancel_task(conn, args.task_id, args.reason, args.cancelled_by)
    elif args.command == "fail":
        result = fail_task(conn, args.task_id, args.error, args.retryable)
    elif args.command == "dispatch":
        result = dispatch_ready_tasks(conn, args.limit)
    elif args.command == "show":
        result = get_task(conn, args.task_id)
    elif args.command == "approve":
        result = resolve_task_approval(
            conn,
            args.task_id,
            args.decision,
            note=args.note,
            resolved_by=args.resolved_by,
        )
    elif args.command == "route":
        result = route_request(args.prompt, args.department_command, top_n=args.top_n)
    elif args.command == "plan":
        result = plan_request(
            conn,
            prompt=args.prompt,
            command=args.department_command,
            created_by=args.created_by,
            source=args.source,
            dispatch=args.dispatch,
        )
    elif args.command == "start":
        result = start_fast_path(
            conn,
            prompt=args.prompt,
            command=args.department_command,
            created_by=args.created_by,
            source=args.source,
            runner_id=args.runner,
            lease_seconds=args.lease_seconds,
        )
    elif args.command == "ai":
        task_id = args.task_id
        if args.prompt:
            if args.dry_run:
                route = route_request(args.prompt, args.department_command)
                owner = route.get("owner")
                if not owner:
                    raise RuntimeError("owner agent could not be resolved")
                preview_task = {
                    "task_id": "dry-run",
                    "title": owner.get("name", owner.get("agent_id", "")),
                    "description": args.prompt,
                    "agent_id": owner.get("agent_id", ""),
                    "payload": {
                        "request": args.prompt,
                        "department_command": args.department_command,
                        "skill_id": (route.get("matched_skill") or {}).get("name", "") or f"agent:{owner.get('agent_id', '')}",
                        "required_context": route.get("required_context", []),
                        "workflow_name": "single-agent-fast-path",
                    },
                }
                result = {
                    "route": route,
                    "execution": preview_ai_task(
                        preview_task,
                        runner_id=args.runner,
                        provider=args.provider,
                        output_paths=args.target_path,
                    ),
                }
            else:
                started = start_fast_path(
                    conn,
                    prompt=args.prompt,
                    command=args.department_command,
                    created_by=args.created_by,
                    source=args.source,
                    runner_id=args.runner,
                    lease_seconds=args.lease_seconds,
                    claim_immediately=False,
                )
                if started.get("status") == "approval_required":
                    result = started
                else:
                    task_id = (started.get("claimed_task") or {}).get("task_id", "")
                    if not task_id:
                        created_tasks = started.get("created_tasks") or []
                        if not created_tasks:
                            raise RuntimeError("ai start did not create a runnable task")
                        task_id = created_tasks[0].get("task_id", "")
                    result = {
                        "started": started,
                        "execution": run_ai_task(
                            conn,
                            task_id=task_id,
                            runner_id=args.runner,
                            provider=args.provider,
                            lease_seconds=args.lease_seconds,
                            model=args.model,
                            timeout_seconds=args.timeout_seconds,
                            dry_run=args.dry_run,
                            output_paths=args.target_path,
                        ),
                    }
        else:
            result = run_ai_task(
                conn,
                task_id=task_id,
                runner_id=args.runner,
                provider=args.provider,
                lease_seconds=args.lease_seconds,
                model=args.model,
                timeout_seconds=args.timeout_seconds,
                dry_run=args.dry_run,
                output_paths=args.target_path,
            )
    elif args.command == "codex":
        task_id = args.task_id
        if args.prompt:
            if args.dry_run:
                route = route_request(args.prompt, args.department_command)
                owner = route.get("owner")
                if not owner:
                    raise RuntimeError("owner agent could not be resolved")
                preview_task = {
                    "task_id": "dry-run",
                    "title": owner.get("name", owner.get("agent_id", "")),
                    "description": args.prompt,
                    "agent_id": owner.get("agent_id", ""),
                    "payload": {
                        "request": args.prompt,
                        "department_command": args.department_command,
                        "skill_id": (route.get("matched_skill") or {}).get("name", "") or f"agent:{owner.get('agent_id', '')}",
                        "required_context": route.get("required_context", []),
                        "workflow_name": "single-agent-fast-path",
                    },
                }
                result = {
                    "route": route,
                    "execution": preview_codex_task(
                        preview_task,
                        runner_id=args.runner,
                        output_paths=args.target_path,
                    ),
                }
            else:
                started = start_fast_path(
                    conn,
                    prompt=args.prompt,
                    command=args.department_command,
                    created_by=args.created_by,
                    source=args.source,
                    runner_id=args.runner,
                    lease_seconds=args.lease_seconds,
                )
                if started.get("status") == "approval_required":
                    result = started
                else:
                    task_id = (started.get("claimed_task") or {}).get("task_id", "")
                    result = {
                        "started": started,
                        "execution": run_codex_task(
                            conn,
                            task_id=task_id,
                            runner_id=args.runner,
                            lease_seconds=args.lease_seconds,
                            model=args.model,
                            timeout_seconds=args.timeout_seconds,
                            dry_run=args.dry_run,
                            output_paths=args.target_path,
                        ),
                    }
        else:
            result = run_codex_task(
                conn,
                task_id=task_id,
                runner_id=args.runner,
                lease_seconds=args.lease_seconds,
                model=args.model,
                timeout_seconds=args.timeout_seconds,
                dry_run=args.dry_run,
                output_paths=args.target_path,
            )
    elif args.command == "sweep":
        result = expire_stale_claims(conn)
    else:
        raise RuntimeError(f"unsupported command: {args.command}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        raise SystemExit(1)
