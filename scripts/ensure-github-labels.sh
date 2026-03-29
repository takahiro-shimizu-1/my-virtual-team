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
ensure_label "copilot" "1F6FEB" "Route this issue to the repository default GitHub coding agent"
ensure_label "claude" "5319E7" "Pin GitHub native execution to the Claude custom agent profile"
ensure_label "codex" "FBCA04" "Pin GitHub native execution to the Codex custom agent profile"
ensure_label "gemini" "0F9D58" "Prefer the local Gemini runner rather than GitHub native execution"
ensure_label "needs-human" "B60205" "Human review or intervention is required"
