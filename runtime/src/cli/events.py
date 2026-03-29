from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
EVENTS_ROOT = SRC_ROOT / "events"
if str(EVENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(EVENTS_ROOT))

from db.connection import connect_db
from db.migrate import apply_migrations
from bus import publish_pending_events


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Runtime event bus CLI")
    parser.add_argument("command", choices=["publish"])
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-rounds", type=int, default=20)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    conn = connect_db()
    apply_migrations(conn)

    if args.command == "publish":
        rounds = []
        total = 0
        while True:
            batch = publish_pending_events(conn, limit=args.limit)
            rounds.append(batch)
            total += batch["count"]
            if args.once or batch["count"] == 0 or len(rounds) >= args.max_rounds:
                break
        result = {
            "published": [item for batch in rounds for item in batch["published"]],
            "count": total,
            "rounds": len(rounds),
            "drained": (rounds[-1]["count"] == 0) if rounds else True,
        }
    else:
        raise RuntimeError(f"unsupported command: {args.command}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
