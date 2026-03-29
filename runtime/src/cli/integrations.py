from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
INTEGRATIONS_ROOT = SRC_ROOT / "integrations"
if str(INTEGRATIONS_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRATIONS_ROOT))

from activity_log import append_activity_entry, build_manual_entry
from github_ops import add_comment, assign_issue, close_issue, create_issue, update_issue
from notion import sync_activity_log
from slack import send_manual_message


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Integration adapter compatibility CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    activity = subparsers.add_parser("activity-log")
    activity.add_argument("--agent-name", required=True)
    activity.add_argument("--department", required=True)
    activity.add_argument("--task", required=True)
    activity.add_argument("--status", required=True)
    activity.add_argument("--output-level", default="高")

    slack = subparsers.add_parser("slack")
    slack.add_argument("--agent", required=True)
    slack.add_argument("--department", required=True)
    slack.add_argument("--task", required=True)
    slack.add_argument("--status", default="完了")

    notion = subparsers.add_parser("notion-sync")
    notion.add_argument("--mode", choices=["today", "all"], default="today")

    github_issue_create = subparsers.add_parser("github-issue-create")
    github_issue_create.add_argument("--title", required=True)
    github_issue_create.add_argument("--body", default="")
    github_issue_create.add_argument("--label", action="append", default=[])
    github_issue_create.add_argument("--assignee", action="append", default=[])
    github_issue_create.add_argument("--milestone", type=int)
    github_issue_create.add_argument("--repo", default="")
    github_issue_create.add_argument("--dry-run", action="store_true")

    github_issue_update = subparsers.add_parser("github-issue-update")
    github_issue_update.add_argument("--issue-number", required=True, type=int)
    github_issue_update.add_argument("--title")
    github_issue_update.add_argument("--body")
    github_issue_update.add_argument("--label", action="append")
    github_issue_update.add_argument("--assignee", action="append")
    github_issue_update.add_argument("--milestone", type=int)
    github_issue_update.add_argument("--state", choices=["open", "closed"])
    github_issue_update.add_argument("--state-reason", choices=["completed", "not_planned"])
    github_issue_update.add_argument("--repo", default="")
    github_issue_update.add_argument("--dry-run", action="store_true")

    github_issue_close = subparsers.add_parser("github-issue-close")
    github_issue_close.add_argument("--issue-number", required=True, type=int)
    github_issue_close.add_argument("--comment", default="")
    github_issue_close.add_argument("--state-reason", choices=["completed", "not_planned"], default="completed")
    github_issue_close.add_argument("--repo", default="")
    github_issue_close.add_argument("--dry-run", action="store_true")

    github_issue_assign = subparsers.add_parser("github-issue-assign")
    github_issue_assign.add_argument("--issue-number", required=True, type=int)
    github_issue_assign.add_argument("--assignee", action="append", required=True)
    github_issue_assign.add_argument("--repo", default="")
    github_issue_assign.add_argument("--dry-run", action="store_true")

    github_comment = subparsers.add_parser("github-comment")
    github_comment.add_argument("--body", required=True)
    github_comment.add_argument("--issue-number", type=int)
    github_comment.add_argument("--pr-number", type=int)
    github_comment.add_argument("--repo", default="")
    github_comment.add_argument("--dry-run", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "activity-log":
        entry = build_manual_entry(
            agent_name=args.agent_name,
            department=args.department,
            task_description=args.task,
            status=args.status,
            output_level=args.output_level,
        )
        result = append_activity_entry(entry)
    elif args.command == "slack":
        result = send_manual_message(
            agent=args.agent,
            department=args.department,
            task=args.task,
            status=args.status,
        )
    elif args.command == "notion-sync":
        result = sync_activity_log(mode=args.mode)
    elif args.command == "github-issue-create":
        result = create_issue(
            title=args.title,
            body=args.body,
            labels=args.label,
            assignees=args.assignee,
            milestone=args.milestone,
            repo=args.repo or None,
            dry_run=args.dry_run,
        )
    elif args.command == "github-issue-update":
        result = update_issue(
            issue_number=args.issue_number,
            title=args.title,
            body=args.body,
            labels=args.label,
            assignees=args.assignee,
            milestone=args.milestone,
            state=args.state,
            state_reason=args.state_reason,
            repo=args.repo or None,
            dry_run=args.dry_run,
        )
    elif args.command == "github-issue-close":
        result = close_issue(
            issue_number=args.issue_number,
            repo=args.repo or None,
            comment=args.comment,
            state_reason=args.state_reason,
            dry_run=args.dry_run,
        )
    elif args.command == "github-issue-assign":
        result = assign_issue(
            issue_number=args.issue_number,
            assignees=args.assignee,
            repo=args.repo or None,
            dry_run=args.dry_run,
        )
    elif args.command == "github-comment":
        result = add_comment(
            body=args.body,
            issue_number=args.issue_number,
            pr_number=args.pr_number,
            repo=args.repo or None,
            dry_run=args.dry_run,
        )
    else:
        raise RuntimeError(f"unsupported command: {args.command}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
