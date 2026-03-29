#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "runtime" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SRC_ROOT / "integrations") not in sys.path:
    sys.path.insert(0, str(SRC_ROOT / "integrations"))

import github_ops


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
            "title,body,url,number",
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


def _run_agent_task(prompt: str, *, repo: str, follow: bool, dry_run: bool) -> dict:
    command = ["gh", "agent-task", "create", prompt, "--repo", repo]
    if follow:
      command.append("--follow")
    if dry_run:
        return {"status": "dry_run", "command": command, "prompt": prompt}
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
    issue.add_argument("--issue-number", type=int, required=True)
    issue.add_argument("--follow", action="store_true")
    issue.add_argument("--dry-run", action="store_true")

    prompt = sub.add_parser("prompt")
    prompt.add_argument("--text", required=True)
    prompt.add_argument("--follow", action="store_true")
    prompt.add_argument("--dry-run", action="store_true")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo
    if not repo:
        raise SystemExit("GitHub repository could not be resolved")

    if args.command == "issue":
        prompt, issue_payload = _prompt_from_issue(repo, args.issue_number)
        result = _run_agent_task(prompt, repo=repo, follow=args.follow, dry_run=args.dry_run)
        payload = {
            "status": result["status"],
            "mode": "issue",
            "repo": repo,
            "issue": issue_payload,
            "result": result,
        }
    else:
        result = _run_agent_task(args.text, repo=repo, follow=args.follow, dry_run=args.dry_run)
        payload = {
            "status": result["status"],
            "mode": "prompt",
            "repo": repo,
            "prompt": args.text,
            "result": result,
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
