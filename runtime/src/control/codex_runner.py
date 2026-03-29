from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from control.task_store import claim_task, complete_task, fail_task, get_task
from registry.catalog import get_agent

REPO_ROOT = Path(__file__).resolve().parents[3]


def _git_changed_paths() -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "git status failed"
        raise RuntimeError(detail)

    changed = []
    for line in completed.stdout.splitlines():
        entry = line.rstrip()
        if not entry:
            continue
        changed.append(entry[3:])
    return changed


def _target_paths(task: dict, explicit_paths: list[str] | None = None) -> list[str]:
    if explicit_paths:
        return [path for path in explicit_paths if path]

    payload = task.get("payload", {}) or {}
    target_paths = payload.get("target_paths", []) or []
    if isinstance(target_paths, list):
        return [path for path in target_paths if isinstance(path, str) and path]
    return []


def _repo_path_exists(path: str) -> bool:
    return (REPO_ROOT / path).exists()


def _build_prompt(task: dict, explicit_paths: list[str] | None = None) -> str:
    payload = task.get("payload", {}) or {}
    request = payload.get("request") or task.get("description") or task.get("title") or ""
    required_context = payload.get("required_context", []) or []
    target_paths = _target_paths(task, explicit_paths)
    agent = get_agent(task.get("agent_id", "")) or {}
    agent_name = agent.get("name") or task.get("agent_id") or "unassigned"
    skill_id = payload.get("skill_id", "")
    context_lines = "\n".join(f"- {path}" for path in required_context[:8]) or "- none"
    target_lines = "\n".join(f"- {path}" for path in target_paths) or "- infer from the request"

    return (
        "You are fulfilling a durable virtual-team task inside the repository.\n"
        "Work only in the current git repo and make the smallest correct change.\n"
        "Do not commit, push, or create branches.\n"
        "If the request is documentation-oriented, edit or create the relevant markdown file directly.\n\n"
        f"Task ID: {task['task_id']}\n"
        f"Agent: {agent_name}\n"
        f"Skill: {skill_id or 'none'}\n"
        f"Title: {task.get('title', '')}\n"
        f"Request:\n{request}\n\n"
        "Preferred target paths:\n"
        f"{target_lines}\n\n"
        "Read this context first when relevant:\n"
        f"{context_lines}\n\n"
        "When you finish, ensure the requested files are updated in the working tree and summarize what changed."
    )


def preview_codex_task(task: dict, *, runner_id: str = "codex", output_paths: list[str] | None = None) -> dict:
    return {
        "status": "dry_run",
        "task_id": task.get("task_id", "dry-run"),
        "runner_id": runner_id,
        "prompt": _build_prompt(task, output_paths),
        "output_paths": _target_paths(task, output_paths),
    }


def _run_codex_exec(prompt: str, *, model: str = "", timeout_seconds: int = 1200) -> dict:
    with tempfile.NamedTemporaryFile(prefix="codex-last-message-", suffix=".txt", delete=False) as handle:
        last_message_path = Path(handle.name)

    command = [
        "codex",
        "-a",
        "never",
        "exec",
        "-C",
        str(REPO_ROOT),
        "-s",
        "workspace-write",
        "-o",
        str(last_message_path),
        prompt,
    ]
    if model:
        command[1:1] = ["-m", model]

    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    last_message = ""
    if last_message_path.exists():
        last_message = last_message_path.read_text(encoding="utf-8").strip()
        last_message_path.unlink(missing_ok=True)

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "codex exec failed"
        raise RuntimeError(detail)

    return {
        "status": "ok",
        "command": command,
        "last_message": last_message,
    }


def run_codex_task(
    conn,
    *,
    task_id: str,
    runner_id: str = "codex",
    lease_seconds: int = 1800,
    model: str = "",
    timeout_seconds: int = 1200,
    dry_run: bool = False,
    output_paths: list[str] | None = None,
) -> dict:
    before_paths = set(_git_changed_paths())
    task = get_task(conn, task_id)

    if dry_run:
        return preview_codex_task(task, runner_id=runner_id, output_paths=output_paths)

    if task["status"] in {"created", "dispatched"}:
        task = claim_task(conn, task_id, runner_id, lease_seconds)
    elif task["status"] == "claimed":
        if task.get("claimed_by") != runner_id:
            raise RuntimeError(f"task is already claimed by {task.get('claimed_by', '')}")
    else:
        raise RuntimeError(f"task is not runnable: {task['status']}")

    prompt = _build_prompt(task, output_paths)

    try:
        codex_result = _run_codex_exec(prompt, model=model, timeout_seconds=timeout_seconds)
        after_paths = set(_git_changed_paths())
        configured_paths = _target_paths(task, output_paths)
        if configured_paths:
            missing = [path for path in configured_paths if not _repo_path_exists(path)]
            if missing:
                raise RuntimeError(f"expected output paths were not created: {', '.join(missing)}")
            changed_paths = configured_paths
        else:
            changed_paths = sorted(after_paths - before_paths)
        if not changed_paths:
            raise RuntimeError("codex completed without producing repository changes")
        completed_task = complete_task(conn, task_id, changed_paths)
        return {
            "status": "completed",
            "task": completed_task,
            "codex": {
                "last_message": codex_result.get("last_message", ""),
            },
            "changed_paths": changed_paths,
        }
    except Exception as exc:
        current = get_task(conn, task_id)
        if current["status"] == "claimed" and current.get("claimed_by") == runner_id:
            failed_task = fail_task(conn, task_id, str(exc), retryable=False)
            return {
                "status": "failed",
                "task": failed_task,
                "error": str(exc),
            }
        raise
