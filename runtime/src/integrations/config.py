from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path.home() / ".config" / "virtual-team" / ".env"


def load_virtual_team_env() -> dict:
    env = dict(os.environ)
    if not ENV_FILE.exists():
        return env

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env.setdefault(key.strip(), value.strip().strip("'").strip('"'))
    return env

