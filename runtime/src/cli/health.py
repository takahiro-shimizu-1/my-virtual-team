from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
HEALTH_ROOT = SRC_ROOT / "health"
if str(HEALTH_ROOT) not in sys.path:
    sys.path.insert(0, str(HEALTH_ROOT))

from db.connection import connect_db
from db.migrate import apply_migrations
from aggregate import build_health_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Runtime health aggregation CLI")
    parser.add_argument("--sweep-timeouts", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    conn = connect_db()
    apply_migrations(conn)
    result = build_health_report(conn, sweep_timeouts=args.sweep_timeouts)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
