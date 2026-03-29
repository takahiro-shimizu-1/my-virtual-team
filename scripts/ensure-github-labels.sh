#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REPO="${1:-}"
if [[ -z "$REPO" ]]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
fi

ensure_label() {
  local name="$1"
  local color="$2"
  local description="$3"
  if gh label list --repo "$REPO" --limit 200 --json name --jq '.[].name' | grep -Fxq "$name"; then
    gh label edit "$name" --repo "$REPO" --color "$color" --description "$description" >/dev/null
  else
    gh label create "$name" --repo "$REPO" --color "$color" --description "$description" >/dev/null
  fi
  echo "label ready: $name"
}

ensure_label "auto" "0E8A16" "Virtual Team native-first automation"
ensure_label "copilot" "1F6FEB" "Route this issue to the default subscription coding agent"
ensure_label "claude" "5319E7" "Run native decomposition flow for this issue"
ensure_label "codex" "FBCA04" "Use native Codex agent route when configured"
ensure_label "needs-human" "B60205" "Human review or intervention is required"
