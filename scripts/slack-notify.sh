#!/bin/bash
# タスク完了時にSlack DMで通知を送るスクリプト
# Usage:
#   ./scripts/slack-notify.sh single <agent> <department> <task> <status>
#
# 事前準備:
#   1. https://api.slack.com/apps でSlack Appを作成
#   2. Bot Token Scopes に chat:write, im:write を追加
#   3. ~/.config/virtual-team/.env に以下を設定:
#      SLACK_BOT_TOKEN=xoxb-xxxx
#      SLACK_USER_ID=U0XXXXXXX（自分のSlackユーザーID）

set -euo pipefail

ENV_FILE="$HOME/.config/virtual-team/.env"

if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    echo "Error: $ENV_FILE が見つかりません。"
    echo "  mkdir -p ~/.config/virtual-team"
    echo "  echo 'SLACK_BOT_TOKEN=xoxb-xxxx' >> ~/.config/virtual-team/.env"
    echo "  echo 'SLACK_USER_ID=U0XXXXXXX' >> ~/.config/virtual-team/.env"
    exit 1
fi

if [ -z "${SLACK_BOT_TOKEN:-}" ] || [ -z "${SLACK_USER_ID:-}" ]; then
    echo "Error: SLACK_BOT_TOKEN と SLACK_USER_ID が必要です。"
    exit 1
fi

# DM用チャンネルIDを取得
DM_CHANNEL=$(curl -s -X POST "https://slack.com/api/conversations.open" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"users\": \"$SLACK_USER_ID\"}" | jq -r '.channel.id')

MODE="${1:-single}"
AGENT="${2:-}"
DEPT="${3:-}"
TASK="${4:-}"
STATUS="${5:-完了}"

case "$STATUS" in
    完了)   ICON=":white_check_mark:" ;;
    進行中) ICON=":arrows_counterclockwise:" ;;
    *)      ICON=":grey_question:" ;;
esac

MSG="$ICON *[$DEPT $AGENT]* $TASK"

curl -s -X POST "https://slack.com/api/chat.postMessage" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"channel\": \"$DM_CHANNEL\", \"text\": \"$MSG\"}" > /dev/null

echo "Slack通知を送信しました。"
