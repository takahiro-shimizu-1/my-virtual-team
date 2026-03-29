from __future__ import annotations

import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from db.connection import STATE_DB_PATH, connect_db
from db.migrate import apply_migrations


def main() -> int:
    conn = connect_db()
    applied = apply_migrations(conn)
    payload = {
        "db_path": str(STATE_DB_PATH),
        "applied": applied,
        "status": "ok",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
