#!/bin/bash
# runtime integration adapter 経由で Notion へ同期する互換ラッパー
# Usage:
#   ./scripts/notion-sync.sh --today   # 今日分を同期
#   ./scripts/notion-sync.sh --all     # 全件同期

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

MODE="${1:---today}"
if [ "$MODE" = "--all" ]; then
  MODE_FLAG="all"
else
  MODE_FLAG="today"
fi

python3 "$ROOT/runtime/src/cli/integrations.py" notion-sync --mode "$MODE_FLAG"
