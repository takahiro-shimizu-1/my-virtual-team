#!/bin/bash
# runtime integration adapter 経由で Slack 通知を送る互換ラッパー
# Usage:
#   ./scripts/slack-notify.sh single <agent> <department> <task> <status>

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

MODE="${1:-single}"
AGENT="${2:-}"
DEPT="${3:-}"
TASK="${4:-}"
STATUS="${5:-完了}"

python3 "$ROOT/runtime/src/cli/integrations.py" slack \
  --agent "$AGENT" \
  --department "$DEPT" \
  --task "$TASK" \
  --status "$STATUS"
