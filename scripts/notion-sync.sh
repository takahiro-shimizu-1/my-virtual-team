#!/bin/bash
# 活動ログをNotionデータベースに同期するスクリプト
# Usage:
#   ./scripts/notion-sync.sh --today   # 今日分を同期
#   ./scripts/notion-sync.sh --all     # 全件同期
#
# 事前準備:
#   1. https://www.notion.so/my-integrations でインテグレーション作成
#   2. Notionに「活動ログ」データベースを作成（カラム: Agent, Department, Task, Status, Date）
#   3. データベースにインテグレーションを接続
#   4. ~/.config/virtual-team/.env に以下を設定:
#      NOTION_API_KEY=ntn_xxxx
#      NOTION_DATABASE_ID=xxxxxxxx

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_ROOT/logs/activity-log.json"
ENV_FILE="$HOME/.config/virtual-team/.env"

if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    echo "Error: $ENV_FILE が見つかりません。"
    echo "  mkdir -p ~/.config/virtual-team"
    echo "  echo 'NOTION_API_KEY=ntn_xxxx' >> ~/.config/virtual-team/.env"
    echo "  echo 'NOTION_DATABASE_ID=xxxxxxxx' >> ~/.config/virtual-team/.env"
    exit 1
fi

if [ -z "${NOTION_API_KEY:-}" ] || [ -z "${NOTION_DATABASE_ID:-}" ]; then
    echo "Error: NOTION_API_KEY と NOTION_DATABASE_ID が必要です。"
    exit 1
fi

MODE="${1:---today}"
TODAY=$(TZ=Asia/Tokyo date +"%Y-%m-%d")

if [ ! -f "$LOG_FILE" ]; then
    echo "活動ログがありません。"
    exit 0
fi

if [ "$MODE" = "--today" ]; then
    ENTRIES=$(jq "[.[] | select(.date == \"$TODAY\")]" "$LOG_FILE")
else
    ENTRIES=$(cat "$LOG_FILE")
fi

COUNT=$(echo "$ENTRIES" | jq 'length')
echo "同期対象: $COUNT 件"

echo "$ENTRIES" | jq -c '.[]' | while read -r entry; do
    AGENT=$(echo "$entry" | jq -r '.agent')
    DEPT=$(echo "$entry" | jq -r '.department')
    TASK=$(echo "$entry" | jq -r '.task')
    STATUS=$(echo "$entry" | jq -r '.status')
    DATE=$(echo "$entry" | jq -r '.date')

    curl -s -X POST "https://api.notion.com/v1/pages" \
        -H "Authorization: Bearer $NOTION_API_KEY" \
        -H "Content-Type: application/json" \
        -H "Notion-Version: 2022-06-28" \
        -d "{
            \"parent\": {\"database_id\": \"$NOTION_DATABASE_ID\"},
            \"properties\": {
                \"Agent\": {\"title\": [{\"text\": {\"content\": \"$AGENT\"}}]},
                \"Department\": {\"rich_text\": [{\"text\": {\"content\": \"$DEPT\"}}]},
                \"Task\": {\"rich_text\": [{\"text\": {\"content\": \"$TASK\"}}]},
                \"Status\": {\"select\": {\"name\": \"$STATUS\"}},
                \"Date\": {\"date\": {\"start\": \"$DATE\"}}
            }
        }" > /dev/null

    echo "  同期: [$DEPT] $AGENT - $TASK"
done

echo "Notion同期完了。"
