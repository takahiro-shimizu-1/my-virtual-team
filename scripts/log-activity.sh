#!/bin/bash
# 仮想社員の活動をJSONログに記録するスクリプト
# Usage: ./scripts/log-activity.sh <agent_name> <department> <task_description> <status> [output_level]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_ROOT/logs/activity-log.json"

AGENT_NAME="${1:?エージェント名を指定してください}"
DEPARTMENT="${2:?部門名を指定してください}"
TASK_DESC="${3:?タスク内容を指定してください}"
STATUS="${4:?ステータスを指定してください (未着手/進行中/完了/保留)}"
OUTPUT_LEVEL="${5:-高}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DATE_JST=$(TZ=Asia/Tokyo date +"%Y-%m-%d")
TIME_JST=$(TZ=Asia/Tokyo date +"%H:%M")

NEW_ENTRY=$(cat <<EOF
{
  "id": "$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || date +%s%N)",
  "timestamp": "$TIMESTAMP",
  "date": "$DATE_JST",
  "time": "$TIME_JST",
  "agent": "$AGENT_NAME",
  "department": "$DEPARTMENT",
  "task": "$TASK_DESC",
  "status": "$STATUS",
  "output_level": "$OUTPUT_LEVEL"
}
EOF
)

mkdir -p "$(dirname "$LOG_FILE")"
if [ ! -f "$LOG_FILE" ] || [ ! -s "$LOG_FILE" ]; then
    echo "[$NEW_ENTRY]" > "$LOG_FILE"
else
    TEMP=$(jq ". += [$NEW_ENTRY]" "$LOG_FILE")
    echo "$TEMP" > "$LOG_FILE"
fi
echo "Activity logged: [$DEPARTMENT] $AGENT_NAME - $TASK_DESC ($STATUS)"
