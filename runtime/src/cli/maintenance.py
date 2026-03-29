from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from control.maintenance import run_maintenance
from db.connection import connect_db
from db.migrate import apply_migrations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintenance loop for watcher, self-improve, events, and health")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--created-by", default="system")
    parser.add_argument("--event-limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    conn = connect_db()
    apply_migrations(conn)

    result = run_maintenance(
        conn,
        recent_days=args.days,
        roots=args.root or None,
        created_by=args.created_by,
        dry_run=args.dry_run,
        event_limit=args.event_limit,
    )
    try:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except BrokenPipeError:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
