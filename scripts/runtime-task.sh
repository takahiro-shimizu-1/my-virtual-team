#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "${VIRTUAL_TEAM_SKIP_ENSURE:-0}" != "1" ]]; then
  bash "$ROOT/scripts/ensure-v4-ready.sh" --quiet --skip-graph --skip-validate
fi
python3 "$ROOT/runtime/src/cli/task.py" "$@"
