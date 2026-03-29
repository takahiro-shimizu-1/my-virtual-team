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
    else:
        raise RuntimeError(f"unsupported command: {args.command}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
