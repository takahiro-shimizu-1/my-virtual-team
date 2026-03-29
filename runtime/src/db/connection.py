from __future__ import annotations

import os
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = REPO_ROOT / ".runtime"
STATE_DB_PATH = RUNTIME_ROOT / "state.db"
EXPORT_ROOT = RUNTIME_ROOT / "exports" / "skill-bus"


def ensure_runtime_dirs() -> None:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)


def resolve_db_path(db_path: str | Path | None = None) -> Path:
    env_path = os.environ.get("VIRTUAL_TEAM_STATE_DB", "").strip()
    if db_path:
        return Path(db_path)
    if env_path:
        return Path(env_path)
    return STATE_DB_PATH


def connect_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    ensure_runtime_dirs()
    path = resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn
