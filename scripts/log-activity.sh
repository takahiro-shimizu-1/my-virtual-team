#!/bin/bash
# runtime integration adapter 経由で活動ログへ記録する互換ラッパー
# Usage: ./scripts/log-activity.sh <agent_name> <department> <task_description> <status> [output_level]

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

AGENT_NAME="${1:?エージェント名を指定してください}"
DEPARTMENT="${2:?部門名を指定してください}"
TASK_DESCRIPTION="${3:?タスク内容を指定してください}"
STATUS="${4:?ステータスを指定してください (未着手/進行中/完了/保留)}"
OUTPUT_LEVEL="${5:-高}"

python3 "$ROOT/runtime/src/cli/integrations.py" activity-log \
  --agent-name "$AGENT_NAME" \
  --department "$DEPARTMENT" \
  --task "$TASK_DESCRIPTION" \
  --status "$STATUS" \
  --output-level "$OUTPUT_LEVEL"
