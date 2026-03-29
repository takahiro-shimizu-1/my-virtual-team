#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "runtime" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SRC_ROOT / "integrations") not in sys.path:
    sys.path.insert(0, str(SRC_ROOT / "integrations"))
if str(SRC_ROOT / "control") not in sys.path:
    sys.path.insert(0, str(SRC_ROOT / "control"))

import github_ops
from control.execution_policy import recommend_execution

LABEL_TO_CUSTOM_AGENT = {
    "auto": "vt-implementation-auto",
    "copilot": "vt-implementation-auto",
    "claude": "vt-implementation-claude",
    "codex": "vt-implementation-codex",
}
UNSUPPORTED_NATIVE_LABELS = {
    "gemini": "GitHub native coding agent does not currently support a Gemini execution path in this repository. Use the local runner: `npm run runtime:task -- ai --provider gemini ...`.",
}


def _prompt_from_issue(repo: str, issue_number: int) -> tuple[str, dict]:
    completed = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--repo",
            repo,
            "--json",
            "title,body,url,number,labels",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    title = (payload.get("title") or "").strip()
    body = (payload.get("body") or "").strip()
    prompt = title if not body else f"{title}\n\n{body}"
    return prompt, payload


def _resolve_issue_custom_agent(
    issue_payload: dict,
    prompt: str,
    explicit_custom_agent: str | None = None,
) -> tuple[str, str]:
    if explicit_custom_agent:
        return explicit_custom_agent, "cli"

    env_override = os.environ.get("VIRTUAL_TEAM_IMPLEMENTATION_AGENT", "").strip()
    if env_override:
        return env_override, "env"

    labels = {
        (item.get("name") or "").strip().lower()
        for item in issue_payload.get("labels", []) or []
        if isinstance(item, dict)
    }
    specific = [name for name in ("claude", "codex", "gemini") if name in labels]
    if len(specific) > 1:
        raise RuntimeError(f"conflicting provider labels: {', '.join(specific)}")
    if "gemini" in labels:
        raise RuntimeError(UNSUPPORTED_NATIVE_LABELS["gemini"])
    if "claude" in labels:
        return LABEL_TO_CUSTOM_AGENT["claude"], "issue-label"
    if "codex" in labels:
        return LABEL_TO_CUSTOM_AGENT["codex"], "issue-label"
    if "copilot" in labels:
        return LABEL_TO_CUSTOM_AGENT["copilot"], "issue-label"
    if "auto" in labels:
        recommendation = recommend_execution(prompt=prompt)
        return recommendation.get("github_profile", LABEL_TO_CUSTOM_AGENT["auto"]), "capability-policy"
    recommendation = recommend_execution(prompt=prompt)
    return recommendation.get("github_profile", LABEL_TO_CUSTOM_AGENT["auto"]), "capability-policy"


def _run_agent_task(
    prompt: str,
    *,
    repo: str,
    follow: bool,
    dry_run: bool,
    custom_agent: str | None = None,
) -> dict:
    command = ["gh", "agent-task", "create", prompt, "--repo", repo]
    if custom_agent:
        command.extend(["--custom-agent", custom_agent])
    if follow:
        command.append("--follow")
    if dry_run:
        return {"status": "dry_run", "command": command, "prompt": prompt, "custom_agent": custom_agent}
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "status": "ok" if completed.returncode == 0 else "error",
        "command": command,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "returncode": completed.returncode,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch GitHub subscription-native agent tasks via gh agent-task")
    parser.add_argument("--repo", default=github_ops.resolve_repository())

    sub = parser.add_subparsers(dest="command", required=True)

    issue = sub.add_parser("issue")
    issue.add_argument("--repo")
    issue.add_argument("--issue-number", type=int, required=True)
    issue.add_argument("--custom-agent", default="")
    issue.add_argument("--follow", action="store_true")
    issue.add_argument("--dry-run", action="store_true")

    prompt = sub.add_parser("prompt")
    prompt.add_argument("--repo")
    prompt.add_argument("--text", required=True)
    prompt.add_argument("--custom-agent", default="")
    prompt.add_argument("--follow", action="store_true")
    prompt.add_argument("--dry-run", action="store_true")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = getattr(args, "repo", None) or github_ops.resolve_repository()
    if not repo:
        raise SystemExit("GitHub repository could not be resolved")

    if args.command == "issue":
        prompt, issue_payload = _prompt_from_issue(repo, args.issue_number)
        custom_agent, source = _resolve_issue_custom_agent(issue_payload, prompt, args.custom_agent or None)
        result = _run_agent_task(
            prompt,
            repo=repo,
            follow=args.follow,
            dry_run=args.dry_run,
            custom_agent=custom_agent,
        )
        payload = {
            "status": result["status"],
            "mode": "issue",
            "repo": repo,
            "issue": issue_payload,
            "selected_custom_agent": custom_agent,
            "custom_agent_source": source,
            "result": result,
        }
    else:
        custom_agent = args.custom_agent.strip() or os.environ.get("VIRTUAL_TEAM_IMPLEMENTATION_AGENT", "").strip()
        source = "cli" if args.custom_agent.strip() else ("env" if custom_agent else "capability-policy")
        if not custom_agent:
            recommendation = recommend_execution(prompt=args.text)
            custom_agent = recommendation.get("github_profile", "") or LABEL_TO_CUSTOM_AGENT["auto"]
        result = _run_agent_task(
            args.text,
            repo=repo,
            follow=args.follow,
            dry_run=args.dry_run,
            custom_agent=custom_agent,
        )
        payload = {
            "status": result["status"],
            "mode": "prompt",
            "repo": repo,
            "prompt": args.text,
            "selected_custom_agent": custom_agent,
            "custom_agent_source": source,
            "result": result,
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
