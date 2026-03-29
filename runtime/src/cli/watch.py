from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from db.connection import connect_db
from db.migrate import apply_migrations
from watchers.local_files import scan_local_assets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local asset watcher CLI")
    parser.add_argument("command", choices=["scan"])
    parser.add_argument("--root", action="append", default=[])
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    conn = connect_db()
    apply_migrations(conn)
    roots = args.root or None

    if args.command == "scan":
        result = scan_local_assets(conn, roots=roots)
    else:
        raise RuntimeError(f"unsupported command: {args.command}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

