from __future__ import annotations

from pathlib import Path

from db.connection import REPO_ROOT

MIGRATIONS_DIR = REPO_ROOT / "runtime" / "migrations"


def ensure_schema_migrations(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version TEXT PRIMARY KEY,
          applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def apply_migrations(conn) -> list[str]:
    ensure_schema_migrations(conn)
    applied = {
        row["version"]
        for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }
    executed = []

    for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = migration_path.name
        if version in applied:
            continue

        sql = migration_path.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, datetime('now'))",
            (version,),
        )
        conn.commit()
        executed.append(version)

    return executed
