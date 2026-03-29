#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="$ROOT/.gitnexus/agent-graph.db"
FORCE="${1:-}"
BUILDER_PY="${GITNEXUS_AGENT_GRAPH_BUILDER:-$ROOT/../gitnexus-stable-ops/lib/agent_graph_builder.py}"
USE_GNI=0

if command -v gni >/dev/null 2>&1; then
  USE_GNI=1
fi

if [[ ! -f "$BUILDER_PY" && "$USE_GNI" -ne 1 ]]; then
  echo "GitNexus builder not found. Set GITNEXUS_AGENT_GRAPH_BUILDER or install gitnexus-stable-ops." >&2
  exit 1
fi

mtime() {
  if stat -c %Y "$1" >/dev/null 2>&1; then
    stat -c %Y "$1"
  else
    stat -f %m "$1"
  fi
}

latest_source_mtime() {
  local latest=0
  local rel path current
  local watch_paths=(
    "agents"
    "guidelines"
    "templates"
    "docs"
    ".claude/rules"
    ".claude/commands"
    ".claude/skills"
    ".gitnexus/workspace.json"
    "AGENTS_CLAUDE.md"
  )

  for rel in "${watch_paths[@]}"; do
    path="$ROOT/$rel"
    if [[ -d "$path" ]]; then
      while IFS= read -r -d '' file; do
        current="$(mtime "$file")"
        if (( current > latest )); then
          latest="$current"
        fi
      done < <(find "$path" -type f -print0)
    elif [[ -f "$path" ]]; then
      current="$(mtime "$path")"
      if (( current > latest )); then
        latest="$current"
      fi
    fi
  done

  echo "$latest"
}

run_agent_index() {
  if [[ -f "$BUILDER_PY" ]]; then
    echo "Building agent graph via $BUILDER_PY"
    python3 "$BUILDER_PY" build "$ROOT" --force
    return 0
  fi

  if [[ "$USE_GNI" -eq 1 ]]; then
    echo "Building agent graph via gni"
    gni agent-index .
    return 0
  fi

  echo "No available agent graph builder." >&2
  exit 1
}

cd "$ROOT"
npm run registry:build >/dev/null

if [[ "$FORCE" == "--force" ]]; then
  echo "Force rebuilding agent graph..."
  run_agent_index
  exit 0
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "Agent graph DB not found. Building..."
  run_agent_index
  exit 0
fi

SOURCE_MTIME="$(latest_source_mtime)"
DB_MTIME="$(mtime "$DB_PATH")"

if (( SOURCE_MTIME > DB_MTIME )); then
  echo "Agent graph is stale. Rebuilding..."
  run_agent_index
else
  echo "Agent graph is fresh. Skipping rebuild."
fi
