#!/bin/bash
# runtime integration adapter 経由で GitHub PR conversation comment を送る互換ラッパー
# Usage:
#   ./scripts/github-pr-comment.sh --pr-number 3 --body "review summary"

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

python3 "$ROOT/runtime/src/cli/integrations.py" github-comment "$@"
