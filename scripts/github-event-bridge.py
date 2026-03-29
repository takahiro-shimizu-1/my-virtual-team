#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "runtime" / "src"
for candidate in (SRC_ROOT, SRC_ROOT / "control", SRC_ROOT / "integrations"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from control.decomposer import decompose_request
from control.router import route_request
import github_ops

BOT_LOGINS = {"github-actions[bot]", "dependabot[bot]"}
COMMAND_CANDIDATES = ["", "strategy", "development", "marketing", "research", "admin"]


def _prompt_text(title: str, body: str) -> str:
    cleaned_title = title.strip()
    cleaned_body = (body or "").strip()
    if cleaned_title and cleaned_body:
        return f"{cleaned_title}\n\n{cleaned_body}"
    return cleaned_title or cleaned_body


def _command_from_comment(body: str) -> tuple[str, str] | None:
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not line.startswith("/vt"):
            return None
        command_line = line[3:].strip()
        if not command_line:
            return ("help", "")
        command, _, remainder = command_line.partition(" ")
        return (command.strip().lower(), remainder.strip())
    return None


def _route_markdown(route: dict, *, prompt: str, source_label: str) -> str:
    owner = route.get("owner") or {}
    skill = route.get("matched_skill") or {}
    execution = route.get("execution_recommendation") or {}
    collaborators = route.get("collaborators", []) or []
    context_lines = [f"- `{path}`" for path in route.get("required_context", [])[:5]] or ["- none"]
    collaborator_lines = [
        f"- {agent.get('name', agent.get('agent_id', ''))} (`{agent.get('agent_id', '')}`)"
        for agent in collaborators[:3]
    ] or ["- none"]
    return "\n".join(
        [
            f"### Virtual Team routing for {source_label}",
            "",
            f"- owner: {owner.get('name', owner.get('agent_id', 'unresolved'))} (`{owner.get('agent_id', '')}`)",
            f"- department: `{owner.get('department', route.get('preferred_department', ''))}`",
            f"- skill: `{skill.get('name', 'none')}`",
            f"- approval_required: `{str(route.get('approval_required', False)).lower()}`",
            f"- execution: `{execution.get('preferred_surface', 'unknown')}` / `{execution.get('local_provider', 'unknown')}` / `{execution.get('github_profile', 'unknown')}`",
            "",
            "**Context**",
            *context_lines,
            "",
            "**Collaborators**",
            *collaborator_lines,
            "",
            f"Prompt snapshot: `{prompt[:120]}`",
            "",
            "Use `/vt plan` to preview multi-phase decomposition.",
        ]
    ).strip()


def _plan_markdown(plan: dict, *, prompt: str, source_label: str) -> str:
    execution = (plan.get("route") or {}).get("execution_recommendation") or {}
    lines = [
        f"### Virtual Team plan preview for {source_label}",
        "",
        f"- workflow: `{plan.get('workflow_name', '')}`",
        f"- phases: `{len(plan.get('tasks', []))}`",
        f"- execution: `{execution.get('preferred_surface', 'unknown')}` / `{execution.get('local_provider', 'unknown')}` / `{execution.get('github_profile', 'unknown')}`",
        "",
    ]
    for index, task in enumerate(plan.get("tasks", []), start=1):
        lines.extend(
            [
                f"{index}. {task.get('title', '')}",
                f"   - agent: `{task.get('agent_id', '')}`",
                f"   - skill: `{task.get('payload', {}).get('skill_id', '')}`",
                f"   - approval_required: `{str(task.get('approval_required', False)).lower()}`",
            ]
        )
    lines.extend(["", f"Prompt snapshot: `{prompt[:120]}`"])
    return "\n".join(lines).strip()


def _help_markdown() -> str:
    return "\n".join(
        [
            "### Virtual Team commands",
            "",
            "- `/vt route` current issue / PR の担当と context を表示",
            "- `/vt plan` current issue / PR の phase plan を dry run 表示",
            "- `/vt route 任意の依頼文` 任意テキストで route",
            "- `/vt plan 任意の依頼文` 任意テキストで plan",
            "- `/vt issue close` issue を閉じる (owner/member/collaborator のみ)",
        ]
    )


def _unresolved_markdown(*, prompt: str, source_label: str, reason: str) -> str:
    return "\n".join(
        [
            f"### Virtual Team routing unavailable for {source_label}",
            "",
            f"- reason: {reason}",
            f"- prompt snapshot: `{prompt[:120]}`",
            "",
            "Try `/vt route 任意の依頼文` or `/vt plan 任意の依頼文` with a more explicit request.",
        ]
    )


def _post_comment(*, repo: str, issue_number: int | None = None, pr_number: int | None = None, body: str, dry_run: bool) -> dict:
    return github_ops.add_comment(
        body=body,
        issue_number=issue_number,
        pr_number=pr_number,
        repo=repo,
        dry_run=dry_run,
    )


def _best_route(prompt: str, *, allow_command_fallback: bool = False) -> dict:
    best_route = None
    best_score = -1
    candidates = COMMAND_CANDIDATES if allow_command_fallback else [""]
    for command in candidates:
        route = route_request(prompt, command)
        owner = route.get("owner")
        if not owner:
            continue
        score = int(owner.get("score", 0))
        if route.get("matched_skill"):
            score += int(route["matched_skill"].get("score", 0))
        if route.get("preferred_department"):
            score += 1
        if score > best_score:
            best_route = route
            best_score = score
    if not best_route:
        raise RuntimeError("owner agent could not be resolved")
    return best_route


def _issue_target(event: dict) -> tuple[str, int, bool]:
    issue = event.get("issue", {}) or {}
    repository = (event.get("repository", {}) or {}).get("full_name", "")
    issue_number = int(issue.get("number", 0))
    is_pr = bool(issue.get("pull_request"))
    return repository, issue_number, is_pr


def _handle_issue_event(event: dict, *, dry_run: bool) -> dict:
    issue = event.get("issue", {}) or {}
    repo, issue_number, _ = _issue_target(event)
    prompt = _prompt_text(issue.get("title", ""), issue.get("body", ""))
    try:
        route = _best_route(prompt)
        comment = _route_markdown(route, prompt=prompt, source_label=f"issue #{issue_number}")
        posted = _post_comment(repo=repo, issue_number=issue_number, body=comment, dry_run=dry_run)
        return {"status": "ok", "action": "issue_routed", "comment": posted, "route": route}
    except RuntimeError as exc:
        posted = _post_comment(
            repo=repo,
            issue_number=issue_number,
            body=_unresolved_markdown(prompt=prompt, source_label=f"issue #{issue_number}", reason=str(exc)),
            dry_run=dry_run,
        )
        return {"status": "ok", "action": "issue_unresolved", "comment": posted}


def _handle_pr_event(event: dict, *, dry_run: bool) -> dict:
    pull_request = event.get("pull_request", {}) or {}
    repo = (event.get("repository", {}) or {}).get("full_name", "")
    pr_number = int(pull_request.get("number", 0))
    prompt = _prompt_text(pull_request.get("title", ""), pull_request.get("body", ""))
    try:
        route = _best_route(prompt)
        comment = _route_markdown(route, prompt=prompt, source_label=f"PR #{pr_number}")
        posted = _post_comment(repo=repo, pr_number=pr_number, body=comment, dry_run=dry_run)
        return {"status": "ok", "action": "pr_routed", "comment": posted, "route": route}
    except RuntimeError as exc:
        posted = _post_comment(
            repo=repo,
            pr_number=pr_number,
            body=_unresolved_markdown(prompt=prompt, source_label=f"PR #{pr_number}", reason=str(exc)),
            dry_run=dry_run,
        )
        return {"status": "ok", "action": "pr_unresolved", "comment": posted}


def _handle_comment_event(event: dict, *, dry_run: bool) -> dict:
    comment = event.get("comment", {}) or {}
    sender = event.get("sender", {}) or {}
    command = _command_from_comment(comment.get("body", ""))
    if not command:
        return {"status": "skipped", "reason": "no_virtual_team_command"}
    if sender.get("login", "") in BOT_LOGINS:
        return {"status": "skipped", "reason": "bot_comment"}

    repo, issue_number, is_pr = _issue_target(event)
    issue = event.get("issue", {}) or {}
    prompt = command[1] or _prompt_text(issue.get("title", ""), issue.get("body", ""))
    association = comment.get("author_association", "")

    if command[0] == "help":
        posted = _post_comment(
            repo=repo,
            issue_number=None if is_pr else issue_number,
            pr_number=issue_number if is_pr else None,
            body=_help_markdown(),
            dry_run=dry_run,
        )
        return {"status": "ok", "action": "help", "comment": posted}

    if command[0] == "route":
        try:
            route = _best_route(prompt, allow_command_fallback=True)
        except RuntimeError as exc:
            posted = _post_comment(
                repo=repo,
                issue_number=None if is_pr else issue_number,
                pr_number=issue_number if is_pr else None,
                body=_unresolved_markdown(
                    prompt=prompt,
                    source_label=f"{'PR' if is_pr else 'issue'} #{issue_number}",
                    reason=str(exc),
                ),
                dry_run=dry_run,
            )
            return {"status": "ok", "action": "route_unresolved", "comment": posted}
        posted = _post_comment(
            repo=repo,
            issue_number=None if is_pr else issue_number,
            pr_number=issue_number if is_pr else None,
            body=_route_markdown(route, prompt=prompt, source_label=f"{'PR' if is_pr else 'issue'} #{issue_number}"),
            dry_run=dry_run,
        )
        return {"status": "ok", "action": "route", "comment": posted, "route": route}

    if command[0] == "plan":
        try:
            plan = decompose_request(prompt, (_best_route(prompt, allow_command_fallback=True).get("command") or None))
        except RuntimeError as exc:
            posted = _post_comment(
                repo=repo,
                issue_number=None if is_pr else issue_number,
                pr_number=issue_number if is_pr else None,
                body=_unresolved_markdown(
                    prompt=prompt,
                    source_label=f"{'PR' if is_pr else 'issue'} #{issue_number}",
                    reason=str(exc),
                ),
                dry_run=dry_run,
            )
            return {"status": "ok", "action": "plan_unresolved", "comment": posted}
        posted = _post_comment(
            repo=repo,
            issue_number=None if is_pr else issue_number,
            pr_number=issue_number if is_pr else None,
            body=_plan_markdown(plan, prompt=prompt, source_label=f"{'PR' if is_pr else 'issue'} #{issue_number}"),
            dry_run=dry_run,
        )
        return {"status": "ok", "action": "plan", "comment": posted, "plan": plan}

    if command[0] == "issue" and command[1].strip().lower() == "close":
        if is_pr:
            return {"status": "skipped", "reason": "issue_close_not_supported_for_pr"}
        if not github_ops.actor_is_trusted(association):
            return {"status": "skipped", "reason": f"untrusted_actor:{association}"}
        result = github_ops.close_issue(
            issue_number=issue_number,
            repo=repo,
            comment="Closed by `/vt issue close`.",
            dry_run=dry_run,
        )
        return {"status": "ok", "action": "issue_close", "result": result}

    posted = _post_comment(
        repo=repo,
        issue_number=None if is_pr else issue_number,
        pr_number=issue_number if is_pr else None,
        body=_help_markdown(),
        dry_run=dry_run,
    )
    return {"status": "ok", "action": "fallback_help", "comment": posted}


def handle_event(event_name: str, event: dict, *, dry_run: bool = False) -> dict:
    if event_name == "issues":
        return _handle_issue_event(event, dry_run=dry_run)
    if event_name in {"pull_request", "pull_request_target"}:
        return _handle_pr_event(event, dry_run=dry_run)
    if event_name == "issue_comment":
        return _handle_comment_event(event, dry_run=dry_run)
    return {"status": "skipped", "reason": f"unsupported_event:{event_name}"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GitHub issue / PR bridge for virtual team routing")
    subparsers = parser.add_subparsers(dest="command", required=True)
    handle = subparsers.add_parser("handle")
    handle.add_argument("--event-name", required=True)
    handle.add_argument("--event-path", required=True)
    handle.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command != "handle":
        raise RuntimeError(f"unsupported command: {args.command}")
    event = json.loads(Path(args.event_path).read_text(encoding="utf-8"))
    result = handle_event(args.event_name, event, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
