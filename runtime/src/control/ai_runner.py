from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from control.task_store import claim_task, complete_task, fail_task, get_task
from registry.catalog import get_agent

REPO_ROOT = Path(__file__).resolve().parents[3]
PROVIDER_ORDER = ("claude", "codex", "gemini")


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    display_name: str
    command: list[str]
    available: bool
    ready: bool
    readiness_reason: str


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


def _command_from_env(name: str) -> list[str]:
    env_name = f"VIRTUAL_TEAM_{name.upper()}_CMD"
    raw = os.environ.get(env_name, "").strip()
    if raw:
        return shlex.split(raw)
    if name == "gemini":
        gemini_bin = shutil.which("gemini")
        if gemini_bin:
            return [gemini_bin]
        if shutil.which("npx"):
            return ["npx", "-y", "@google/gemini-cli"]
    return [name]


def _command_available(command: list[str]) -> bool:
    if not command:
        return False
    if Path(command[0]).is_absolute():
        return Path(command[0]).exists()
    return shutil.which(command[0]) is not None


def _provider_readiness(name: str, *, available: bool) -> tuple[bool, str]:
    if not available:
        return False, "command not found"
    if name != "gemini":
        return True, ""
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") or os.environ.get("GOOGLE_GENAI_USE_GCA"):
        return True, "environment-configured"
    settings_path = Path.home() / ".gemini" / "settings.json"
    if settings_path.exists():
        return True, str(settings_path)
    return False, "Gemini CLI is installed but auth is not configured"


def resolve_local_provider(
    provider: str = "auto",
    *,
    require_available: bool = True,
    require_ready: bool = False,
) -> ProviderSpec:
    requested = (provider or "auto").strip().lower()
    if requested and requested != "auto" and requested not in PROVIDER_ORDER:
        raise RuntimeError(f"unsupported provider: {requested}")

    if requested == "auto":
        preferred = (os.environ.get("VIRTUAL_TEAM_LOCAL_AI_PROVIDER", "") or "").strip().lower()
        candidates = [preferred] + [name for name in PROVIDER_ORDER if name != preferred] if preferred else list(PROVIDER_ORDER)
    else:
        candidates = [requested]

    last_spec: ProviderSpec | None = None
    for name in candidates:
        command = _command_from_env(name)
        spec = ProviderSpec(
            name=name,
            display_name={
                "claude": "Claude Code",
                "codex": "Codex",
                "gemini": "Gemini CLI",
            }[name],
            command=command,
            available=_command_available(command),
            ready=False,
            readiness_reason="",
        )
        ready, readiness_reason = _provider_readiness(name, available=spec.available)
        spec = ProviderSpec(
            name=spec.name,
            display_name=spec.display_name,
            command=spec.command,
            available=spec.available,
            ready=ready,
            readiness_reason=readiness_reason,
        )
        if spec.available and (spec.ready or not require_ready):
            return spec
        last_spec = spec

    if last_spec and not require_available and not require_ready:
        return last_spec
    if requested == "auto":
        if require_ready:
            raise RuntimeError("no local AI runner is ready; tried claude, codex, gemini")
        raise RuntimeError("no local AI runner is available; tried claude, codex, gemini")
    if require_ready:
        raise RuntimeError(f"requested provider is not ready: {requested}")
    raise RuntimeError(f"requested provider is not available: {requested}")


def available_local_providers() -> list[dict]:
    items = []
    for name in PROVIDER_ORDER:
        spec = resolve_local_provider(name, require_available=False)
        items.append(
            {
                "provider": spec.name,
                "display_name": spec.display_name,
                "command": spec.command,
                "available": spec.available,
                "ready": spec.ready,
                "readiness_reason": spec.readiness_reason,
            }
        )
    return items


def preview_ai_task(
    task: dict,
    *,
    runner_id: str = "local-ai",
    provider: str = "auto",
    output_paths: list[str] | None = None,
) -> dict:
    spec = resolve_local_provider(provider, require_available=False)
    return {
        "status": "dry_run",
        "task_id": task.get("task_id", "dry-run"),
        "runner_id": runner_id,
        "provider": spec.name,
        "provider_available": spec.available,
        "provider_ready": spec.ready,
        "provider_reason": spec.readiness_reason,
        "provider_command": spec.command,
        "available_providers": available_local_providers(),
        "prompt": _build_prompt(task, output_paths),
        "output_paths": _target_paths(task, output_paths),
    }


def _parse_json_payload(stdout: str) -> dict:
    raw = stdout.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise RuntimeError("AI CLI returned non-JSON output")


def _run_codex_exec(spec: ProviderSpec, prompt: str, *, model: str = "", timeout_seconds: int = 1200) -> dict:
    with tempfile.NamedTemporaryFile(prefix="codex-last-message-", suffix=".txt", delete=False) as handle:
        last_message_path = Path(handle.name)

    command = [
        *spec.command,
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
        "provider": spec.name,
        "command": command,
        "summary": last_message,
        "stdout": completed.stdout.strip(),
    }


def _run_claude_exec(spec: ProviderSpec, prompt: str, *, model: str = "", timeout_seconds: int = 1200) -> dict:
    command = [*spec.command, "-p", "--permission-mode", "acceptEdits", "--output-format", "json"]
    if model:
        command.extend(["--model", model])
    command.append(prompt)

    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "claude print failed"
        raise RuntimeError(detail)

    payload = _parse_json_payload(completed.stdout)
    if payload.get("is_error"):
        raise RuntimeError(payload.get("result") or payload.get("error") or "claude returned error")

    return {
        "provider": spec.name,
        "command": command,
        "summary": payload.get("result", "").strip(),
        "raw": payload,
    }


def _run_gemini_exec(spec: ProviderSpec, prompt: str, *, model: str = "", timeout_seconds: int = 1200) -> dict:
    command = [*spec.command, "--prompt", prompt, "--output-format", "json", "--yolo"]
    if model:
        command.extend(["--model", model])

    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "gemini headless run failed"
        raise RuntimeError(detail)

    payload = _parse_json_payload(completed.stdout)
    error = payload.get("error") or {}
    if error:
        raise RuntimeError(error.get("message") or "gemini returned error")

    return {
        "provider": spec.name,
        "command": command,
        "summary": (payload.get("response") or "").strip(),
        "raw": payload,
    }


def _run_provider_exec(spec: ProviderSpec, prompt: str, *, model: str = "", timeout_seconds: int = 1200) -> dict:
    if spec.name == "codex":
        return _run_codex_exec(spec, prompt, model=model, timeout_seconds=timeout_seconds)
    if spec.name == "claude":
        return _run_claude_exec(spec, prompt, model=model, timeout_seconds=timeout_seconds)
    if spec.name == "gemini":
        return _run_gemini_exec(spec, prompt, model=model, timeout_seconds=timeout_seconds)
    raise RuntimeError(f"unsupported provider: {spec.name}")


def run_ai_task(
    conn,
    *,
    task_id: str,
    runner_id: str = "local-ai",
    provider: str = "auto",
    lease_seconds: int = 1800,
    model: str = "",
    timeout_seconds: int = 1200,
    dry_run: bool = False,
    output_paths: list[str] | None = None,
) -> dict:
    task = get_task(conn, task_id)
    spec = resolve_local_provider(provider, require_available=not dry_run, require_ready=not dry_run)
    effective_runner_id = runner_id or f"{spec.name}-local"
    if effective_runner_id == "local-ai":
        effective_runner_id = f"{spec.name}-local"

    if dry_run:
        return preview_ai_task(task, runner_id=effective_runner_id, provider=spec.name, output_paths=output_paths)

    before_paths = set(_git_changed_paths())

    if task["status"] in {"created", "dispatched"}:
        task = claim_task(conn, task_id, effective_runner_id, lease_seconds)
    elif task["status"] == "claimed":
        if task.get("claimed_by") != effective_runner_id:
            raise RuntimeError(f"task is already claimed by {task.get('claimed_by', '')}")
    else:
        raise RuntimeError(f"task is not runnable: {task['status']}")

    prompt = _build_prompt(task, output_paths)

    try:
        provider_result = _run_provider_exec(spec, prompt, model=model, timeout_seconds=timeout_seconds)
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
            raise RuntimeError(f"{spec.name} completed without producing repository changes")
        completed_task = complete_task(conn, task_id, changed_paths)
        return {
            "status": "completed",
            "task": completed_task,
            "provider": {
                "name": spec.name,
                "display_name": spec.display_name,
                "command": spec.command,
                "summary": provider_result.get("summary", ""),
            },
            "changed_paths": changed_paths,
        }
    except Exception as exc:
        current = get_task(conn, task_id)
        if current["status"] == "claimed" and current.get("claimed_by") == effective_runner_id:
            failed_task = fail_task(conn, task_id, str(exc), retryable=False)
            return {
                "status": "failed",
                "task": failed_task,
                "error": str(exc),
            }
        raise
