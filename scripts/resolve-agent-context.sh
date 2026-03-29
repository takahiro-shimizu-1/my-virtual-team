#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="$ROOT/.gitnexus/agent-graph.db"
RESOLVER_PY="${GITNEXUS_CONTEXT_RESOLVER:-$ROOT/../gitnexus-stable-ops/lib/context_resolver.py}"

if [[ $# -lt 1 ]]; then
  echo "Usage: bash scripts/resolve-agent-context.sh \"query\" [extra args...]" >&2
  exit 1
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "Agent graph DB not found. Run: npm run graph:build" >&2
  exit 1
fi

if [[ ! -f "$RESOLVER_PY" ]]; then
  echo "Context resolver not found. Set GITNEXUS_CONTEXT_RESOLVER or install gitnexus-stable-ops." >&2
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
