#!/bin/bash
# runtime integration adapter 経由で GitHub Issue を操作する互換ラッパー
# Usage examples:
#   ./scripts/github-issue.sh github-issue-create --title "New task" --body "body"
#   ./scripts/github-issue.sh github-issue-update --issue-number 12 --state closed

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

python3 "$ROOT/runtime/src/cli/integrations.py" "$@"
