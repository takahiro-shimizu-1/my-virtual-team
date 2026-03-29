#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="$ROOT/.gitnexus/agent-graph.db"
LOCAL_RESOLVER_PY="$ROOT/runtime/src/gitnexus/context_resolver.py"
RESOLVER_PY="${GITNEXUS_CONTEXT_RESOLVER:-}"

if [[ $# -lt 1 ]]; then
  echo "Usage: bash scripts/resolve-agent-context.sh \"query\" [extra args...]" >&2
  exit 1
fi

if [[ -z "$RESOLVER_PY" ]]; then
  if [[ -f "$LOCAL_RESOLVER_PY" ]]; then
    RESOLVER_PY="$LOCAL_RESOLVER_PY"
  fi
fi

if [[ "${VIRTUAL_TEAM_SKIP_ENSURE:-0}" != "1" ]]; then
  bash "$ROOT/scripts/ensure-v4-ready.sh" --quiet --skip-migrate --skip-validate
fi

if [[ ! -f "$RESOLVER_PY" ]]; then
  echo "Context resolver not found. Use the repo-local runtime/src/gitnexus copy or set GITNEXUS_CONTEXT_RESOLVER." >&2
  exit 1
fi

QUERY="$1"
shift

EXTRA_ARGS=("$@")
HAS_DEPTH=0

for arg in "${EXTRA_ARGS[@]}"; do
  if [[ "$arg" == "--depth" ]]; then
    HAS_DEPTH=1
    break
  fi
done

if [[ "$HAS_DEPTH" -eq 0 ]]; then
  EXTRA_ARGS=(--depth 1 "${EXTRA_ARGS[@]}")
fi

python3 "$RESOLVER_PY" "$QUERY" --repo "$ROOT" --db "$DB_PATH" "${EXTRA_ARGS[@]}"
