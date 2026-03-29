from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from db.connection import REPO_ROOT

DEFAULT_ROOTS = ["agents", "guidelines", "templates", ".claude/rules"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_root(root: str | Path) -> Path:
    path = Path(root)
    return path if path.is_absolute() else REPO_ROOT / path


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def scan_local_assets(conn, roots: list[str] | None = None) -> dict:
    roots = roots or DEFAULT_ROOTS
    current = {}
    for root in roots:
        root_path = _resolve_root(root)
        if not root_path.exists():
            continue
        for path in sorted(root_path.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else str(path)
            current[relative] = _hash_file(path)

    previous = {
        row["path"]: row["content_hash"]
        for row in conn.execute("SELECT path, content_hash FROM watch_sources").fetchall()
    }

    changes = []
    now = _now_iso()

    for relative, digest in current.items():
        old_digest = previous.get(relative)
        if old_digest == digest:
            conn.execute(
                "UPDATE watch_sources SET last_seen_at = ? WHERE path = ?",
                (now, relative),
            )
            continue

        diff_type = "created" if old_digest is None else "updated"
        detail = {
            "path": relative,
            "previous_hash": old_digest or "",
            "current_hash": digest,
        }
        conn.execute(
            "INSERT INTO knowledge_diffs (path, diff_type, detail_json, created_at) VALUES (?, ?, ?, ?)",
            (relative, diff_type, json.dumps(detail, ensure_ascii=False), now),
        )
        conn.execute(
            """
            INSERT INTO watch_sources (path, content_hash, last_seen_at, last_changed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
              content_hash = excluded.content_hash,
              last_seen_at = excluded.last_seen_at,
              last_changed_at = excluded.last_changed_at
            """,
            (relative, digest, now, now),
        )
        changes.append({"path": relative, "diff_type": diff_type})

    for relative in sorted(set(previous) - set(current)):
        detail = {
            "path": relative,
            "previous_hash": previous[relative],
            "current_hash": "",
        }
        conn.execute(
            "INSERT INTO knowledge_diffs (path, diff_type, detail_json, created_at) VALUES (?, 'deleted', ?, ?)",
            (relative, json.dumps(detail, ensure_ascii=False), now),
        )
        conn.execute("DELETE FROM watch_sources WHERE path = ?", (relative,))
        changes.append({"path": relative, "diff_type": "deleted"})

    conn.commit()
    return {
        "roots": roots,
        "scanned_files": len(current),
        "changes": changes,
    }

