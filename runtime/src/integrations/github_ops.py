from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from config import load_virtual_team_env
from db.connection import REPO_ROOT

REMOTE_PATTERNS = [
    re.compile(r"^git@github\.com:(?P<repo>[^/]+/[^/]+?)(?:\.git)?$"),
    re.compile(r"^https?://github\.com/(?P<repo>[^/]+/[^/]+?)(?:\.git)?/?$"),
    re.compile(r"^ssh://git@github\.com/(?P<repo>[^/]+/[^/]+?)(?:\.git)?/?$"),
]

TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}


def _normalized_env(env: dict | None = None) -> dict:
    resolved = dict(env or load_virtual_team_env())
    if resolved.get("GITHUB_TOKEN") and not resolved.get("GH_TOKEN"):
        resolved["GH_TOKEN"] = resolved["GITHUB_TOKEN"]
    resolved.setdefault("GH_PROMPT_DISABLED", "1")
    resolved.setdefault("GIT_TERMINAL_PROMPT", "0")
    return resolved


def _parse_remote_repo(remote_url: str) -> str:
    candidate = remote_url.strip()
    for pattern in REMOTE_PATTERNS:
        match = pattern.match(candidate)
        if match:
            return match.group("repo")
    return ""


def resolve_repository(env: dict | None = None, cwd: str | Path | None = None) -> str:
    resolved_env = _normalized_env(env)
    for key in ("VIRTUAL_TEAM_GITHUB_REPOSITORY", "GITHUB_REPOSITORY"):
        value = resolved_env.get(key, "").strip()
        if value:
            return value

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=Path(cwd) if cwd else REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return _parse_remote_repo(result.stdout)


def _require_repository(repo: str | None = None, env: dict | None = None) -> str:
    resolved = (repo or resolve_repository(env=env)).strip()
    if not resolved:
        raise RuntimeError("GitHub repository could not be resolved")
    return resolved


def _run_gh_api(
    endpoint: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    env: dict | None = None,
    dry_run: bool = False,
) -> dict:
    resolved_env = _normalized_env(env)
    command = ["gh", "api", "--method", method.upper(), endpoint]

    if dry_run:
        return {
            "status": "dry_run",
            "command": command,
            "payload": payload or {},
        }

    temp_path: str | None = None
    try:
        if payload is not None:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
                json.dump(payload, handle, ensure_ascii=False)
                handle.flush()
                temp_path = handle.name
            command.extend(["--input", temp_path])

        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=resolved_env,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("gh CLI is not installed") from exc
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"gh api failed: {endpoint}"
        raise RuntimeError(detail)

    body = completed.stdout.strip()
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"raw": body}


def _optional_int(value) -> int | None:
    if value in (None, "", 0):
        return None
    return int(value)


def _clean_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    if not values:
        return []
    return [value.strip() for value in values if value and value.strip()]


def _graphql(query: str, *, env: dict | None = None, dry_run: bool = False) -> dict:
    resolved_env = _normalized_env(env)
    command = ["gh", "api", "graphql", "-f", f"query={query}"]
    if dry_run:
        return {"status": "dry_run", "command": command}
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=resolved_env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "gh graphql failed"
        raise RuntimeError(detail)
    body = completed.stdout.strip()
    return json.loads(body) if body else {}


def _graphql_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _suggested_actor_ids(repository: str, logins: list[str], env: dict | None = None) -> dict[str, str]:
    if not logins:
        return {}
    owner, repo_name = repository.split("/", 1)
    login_names = ",".join(sorted(set(logins)))
    query = (
        "query { repository(owner:%s, name:%s) { suggestedActors(capabilities:[CAN_BE_ASSIGNED], loginNames:%s, first: 20) "
        "{ nodes { __typename ... on User { id login } ... on Bot { id login } } } } }"
        % (_graphql_string(owner), _graphql_string(repo_name), _graphql_string(login_names))
    )
    data = _graphql(query, env=env).get("data", {})
    nodes = (((data.get("repository") or {}).get("suggestedActors") or {}).get("nodes") or [])
    return {node["login"].lower(): node["id"] for node in nodes if node.get("login") and node.get("id")}


def _issue_node_id(repository: str, issue_number: int, env: dict | None = None) -> str:
    owner, repo_name = repository.split("/", 1)
    query = (
        "query { repository(owner:%s, name:%s) { issue(number:%d) { id } } }"
        % (_graphql_string(owner), _graphql_string(repo_name), issue_number)
    )
    data = _graphql(query, env=env).get("data", {})
    issue = ((data.get("repository") or {}).get("issue") or {})
    node_id = issue.get("id", "")
    if not node_id:
        raise RuntimeError(f"issue node id could not be resolved: {issue_number}")
    return node_id


def assign_issue(
    *,
    issue_number: int,
    assignees: list[str],
    repo: str | None = None,
    env: dict | None = None,
    dry_run: bool = False,
) -> dict:
    repository = _require_repository(repo, env)
    cleaned = _clean_list(assignees)
    if not cleaned:
        return {"status": "skipped", "reason": "no_assignees"}
    if dry_run:
        return {
            "status": "dry_run",
            "repo": repository,
            "issue_number": issue_number,
            "assignees": cleaned,
        }

    actor_ids = _suggested_actor_ids(repository, cleaned, env=env)
    missing = [login for login in cleaned if login.lower() not in actor_ids]
    if missing:
        raise RuntimeError(f"assignable actors could not be resolved: {', '.join(missing)}")

    issue_id = _issue_node_id(repository, issue_number, env=env)
    quoted_ids = ", ".join(_graphql_string(actor_ids[login.lower()]) for login in cleaned)
    mutation = (
        "mutation { addAssigneesToAssignable(input:{assignableId:%s, assigneeIds:[%s]}) "
        "{ assignable { ... on Issue { number assignees(first:20){ nodes { login } } } } } }"
        % (_graphql_string(issue_id), quoted_ids)
    )
    data = _graphql(mutation, env=env).get("data", {})
    assignees_result = (
        (((data.get("addAssigneesToAssignable") or {}).get("assignable") or {}).get("assignees") or {}).get("nodes")
        or []
    )
    return {
        "status": "assigned",
        "repo": repository,
        "issue_number": issue_number,
        "assignees": [node.get("login", "") for node in assignees_result],
    }


def create_issue(
    *,
    title: str,
    body: str = "",
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    milestone: int | None = None,
    repo: str | None = None,
    env: dict | None = None,
    dry_run: bool = False,
) -> dict:
    repository = _require_repository(repo, env)
    payload = {
        "title": title,
        "body": body,
    }
    cleaned_labels = _clean_list(labels)
    if cleaned_labels:
        payload["labels"] = cleaned_labels
    cleaned_assignees = _clean_list(assignees)
    if milestone is not None:
        payload["milestone"] = milestone

    response = _run_gh_api(
        f"repos/{repository}/issues",
        method="POST",
        payload=payload,
        env=env,
        dry_run=dry_run,
    )
    if dry_run:
        return {
            "status": "dry_run",
            "repo": repository,
            "title": title,
            "payload": payload,
        }
    result = {
        "status": "created",
        "repo": repository,
        "issue_number": response.get("number"),
        "url": response.get("html_url", ""),
        "title": response.get("title", title),
    }
    if cleaned_assignees:
        result["assignment"] = assign_issue(
            issue_number=result["issue_number"],
            assignees=cleaned_assignees,
            repo=repository,
            env=env,
            dry_run=dry_run,
        )
    return result


def update_issue(
    *,
    issue_number: int,
    title: str | None = None,
    body: str | None = None,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    milestone: int | None = None,
    state: str | None = None,
    state_reason: str | None = None,
    repo: str | None = None,
    env: dict | None = None,
    dry_run: bool = False,
) -> dict:
    repository = _require_repository(repo, env)
    payload: dict[str, object] = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    cleaned_labels = _clean_list(labels)
    if labels is not None:
        payload["labels"] = cleaned_labels
    cleaned_assignees = _clean_list(assignees)
    if assignees is not None:
        payload["assignees"] = cleaned_assignees
    if milestone is not None:
        payload["milestone"] = milestone
    if state is not None:
        payload["state"] = state
    if state == "closed" and state_reason is not None:
        payload["state_reason"] = state_reason
    if not payload:
        raise RuntimeError("issue update requires at least one field")

    response = _run_gh_api(
        f"repos/{repository}/issues/{issue_number}",
        method="PATCH",
        payload=payload,
        env=env,
        dry_run=dry_run,
    )
    if dry_run:
        return {
            "status": "dry_run",
            "repo": repository,
            "issue_number": issue_number,
            "payload": payload,
        }
    return {
        "status": "updated",
        "repo": repository,
        "issue_number": response.get("number", issue_number),
        "state": response.get("state", state or ""),
        "url": response.get("html_url", ""),
    }


def add_comment(
    *,
    body: str,
    issue_number: int | None = None,
    pr_number: int | None = None,
    repo: str | None = None,
    env: dict | None = None,
    dry_run: bool = False,
) -> dict:
    repository = _require_repository(repo, env)
    if bool(issue_number) == bool(pr_number):
        raise RuntimeError("comment target requires exactly one of issue_number or pr_number")
    target_number = issue_number or pr_number
    target_kind = "pull_request" if pr_number else "issue"
    response = _run_gh_api(
        f"repos/{repository}/issues/{target_number}/comments",
        method="POST",
        payload={"body": body},
        env=env,
        dry_run=dry_run,
    )
    if dry_run:
        return {
            "status": "dry_run",
            "repo": repository,
            "target_kind": target_kind,
            "target_number": target_number,
            "body": body,
        }
    return {
        "status": "commented",
        "repo": repository,
        "target_kind": target_kind,
        "target_number": target_number,
        "external_id": str(response.get("id", "")),
        "url": response.get("html_url", ""),
    }


def close_issue(
    *,
    issue_number: int,
    repo: str | None = None,
    env: dict | None = None,
    comment: str = "",
    state_reason: str = "completed",
    dry_run: bool = False,
) -> dict:
    repository = _require_repository(repo, env)
    comment_result = None
    if comment:
        comment_result = add_comment(
            body=comment,
            issue_number=issue_number,
            repo=repository,
            env=env,
            dry_run=dry_run,
        )
    update_result = update_issue(
        issue_number=issue_number,
        state="closed",
        state_reason=state_reason,
        repo=repository,
        env=env,
        dry_run=dry_run,
    )
    return {
        "status": "dry_run" if dry_run else "closed",
        "repo": repository,
        "issue_number": issue_number,
        "comment": comment_result,
        "update": update_result,
    }


def _target_from_task(task: dict) -> dict:
    payload = task.get("payload", {}) or {}
    github_payload = payload.get("github", {}) or {}
    repo = (
        github_payload.get("repo")
        or payload.get("github_repo")
        or payload.get("repository")
        or ""
    )
    return {
        "repo": repo,
        "issue_number": _optional_int(
            github_payload.get("issue_number") or payload.get("github_issue_number")
        ),
        "pr_number": _optional_int(
            github_payload.get("pr_number") or payload.get("github_pr_number")
        ),
        "close_on_complete": bool(
            github_payload.get("close_on_complete") or payload.get("github_close_on_complete")
        ),
    }


def has_notification_target(payload: dict) -> bool:
    target = _target_from_task(payload.get("task", {}) or {})
    return bool(target.get("issue_number") or target.get("pr_number"))


def _task_outputs_lines(task: dict) -> list[str]:
    outputs = task.get("outputs", []) or []
    if not outputs:
        return ["- outputs: none"]
    return [f"- output: `{item.get('path', '')}` ({item.get('kind', 'artifact')})" for item in outputs]


def _notification_body(notification: dict) -> str:
    payload = notification["payload"]
    event = payload.get("event", {})
    task = payload.get("task", {})
    agent = payload.get("agent", {})
    event_type = event.get("event_type", "")
    status_title = {
        "task.completed": "Task completed",
        "task.failed": "Task failed",
        "task.timeout": "Task timed out",
        "approval.requested": "Approval requested",
    }.get(event_type, event_type or "Task update")
    lines = [
        f"### Virtual Team: {status_title}",
        "",
        f"- task: {task.get('title', '')}",
        f"- task_id: `{task.get('task_id', '')}`",
        f"- agent: {agent.get('name', task.get('agent_id', ''))}",
        f"- workflow: `{task.get('workflow_id', '') or 'single'}`",
        f"- source: `{task.get('source', '')}`",
        f"- state: `{task.get('status', '')}`",
    ]
    lines.extend(_task_outputs_lines(task))
    error_message = task.get("error_message", "")
    if error_message:
        lines.append(f"- error: {error_message}")
    note = (event.get("payload") or {}).get("note", "")
    if note:
        lines.append(f"- note: {note}")
    return "\n".join(lines).strip()


def deliver_notification(notification: dict) -> dict:
    payload = notification["payload"]
    task = payload.get("task", {}) or {}
    target = _target_from_task(task)
    repo = target.get("repo") or resolve_repository()
    issue_number = target.get("issue_number")
    pr_number = target.get("pr_number")
    if not repo:
        return {"status": "skipped", "reason": "missing_github_repository"}
    if not issue_number and not pr_number:
        return {"status": "skipped", "reason": "missing_github_target"}

    try:
        comment_result = add_comment(
            body=_notification_body(notification),
            issue_number=issue_number,
            pr_number=pr_number,
            repo=repo,
        )
        result = {
            "status": "sent",
            "external_id": comment_result.get("external_id", ""),
            "detail": comment_result,
        }
        if issue_number and target.get("close_on_complete") and payload.get("event", {}).get("event_type") == "task.completed":
            result["close_result"] = close_issue(issue_number=issue_number, repo=repo)
        return result
    except RuntimeError as exc:
        return {"status": "error", "reason": str(exc)}


def actor_is_trusted(association: str) -> bool:
    return association.upper() in TRUSTED_ASSOCIATIONS
