from __future__ import annotations

import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = REPO_ROOT / ".runtime"
STATE_DB_PATH = RUNTIME_ROOT / "state.db"
EXPORT_ROOT = RUNTIME_ROOT / "exports" / "skill-bus"


def ensure_runtime_dirs() -> None:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)


def connect_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    ensure_runtime_dirs()
    path = Path(db_path) if db_path else STATE_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn
