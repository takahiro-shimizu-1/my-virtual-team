from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from control.skill_monitor import analyze_skill_health, enqueue_improvement_tasks
from db.connection import connect_db
from db.migrate import apply_migrations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Skill health analysis and self-improve task enqueue")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze")
    analyze.add_argument("--days", type=int, default=7)

    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("--days", type=int, default=7)
    enqueue.add_argument("--created-by", default="system")
    enqueue.add_argument("--source", default="self-improve")
    enqueue.add_argument("--dry-run", action="store_true")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    conn = connect_db()
    apply_migrations(conn)

    if args.command == "analyze":
        result = {"status": "ok", "skills": analyze_skill_health(conn, recent_days=args.days)}
    else:
        result = enqueue_improvement_tasks(
            conn,
            recent_days=args.days,
            created_by=args.created_by,
            source=args.source,
            dry_run=args.dry_run,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
