#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="$ROOT/.gitnexus/agent-graph.db"
BUILDER_PY="${GITNEXUS_AGENT_GRAPH_BUILDER:-$ROOT/../gitnexus-stable-ops/lib/agent_graph_builder.py}"
USE_GNI=0
FORCE=0
QUIET=0

for arg in "$@"; do
  case "$arg" in
    --force)
      FORCE=1
      ;;
    --quiet)
      QUIET=1
      ;;
  esac
done

if command -v gni >/dev/null 2>&1; then
  USE_GNI=1
fi

if [[ ! -f "$BUILDER_PY" && "$USE_GNI" -ne 1 ]]; then
  echo "GitNexus builder not found. Set GITNEXUS_AGENT_GRAPH_BUILDER or install gitnexus-stable-ops." >&2
  exit 1
fi

say() {
  if [[ "$QUIET" -ne 1 ]]; then
    echo "$@"
  fi
}

run_quietly() {
  local stderr_file
  stderr_file="$(mktemp)"
  if "$@" >/dev/null 2>"$stderr_file"; then
    rm -f "$stderr_file"
    return 0
  fi
  cat "$stderr_file" >&2
  rm -f "$stderr_file"
  return 1
}

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
    say "Building agent graph via $BUILDER_PY"
    if [[ "$QUIET" -eq 1 ]]; then
      run_quietly python3 "$BUILDER_PY" build "$ROOT" --force
    else
      python3 "$BUILDER_PY" build "$ROOT" --force
    fi
    return 0
  fi

  if [[ "$USE_GNI" -eq 1 ]]; then
    say "Building agent graph via gni"
    if [[ "$QUIET" -eq 1 ]]; then
      run_quietly gni agent-index .
    else
      gni agent-index .
    fi
    return 0
  fi

  echo "No available agent graph builder." >&2
  exit 1
}

cd "$ROOT"
if [[ "${SKIP_REGISTRY_BUILD:-0}" != "1" ]]; then
  if [[ "$QUIET" -eq 1 ]]; then
    run_quietly npm run registry:build
  else
    npm run registry:build
  fi
fi

if [[ "$FORCE" -eq 1 ]]; then
  say "Force rebuilding agent graph..."
  run_agent_index
  exit 0
fi

if [[ ! -f "$DB_PATH" ]]; then
  say "Agent graph DB not found. Building..."
  run_agent_index
  exit 0
fi

SOURCE_MTIME="$(latest_source_mtime)"
DB_MTIME="$(mtime "$DB_PATH")"

if (( SOURCE_MTIME > DB_MTIME )); then
  say "Agent graph is stale. Rebuilding..."
  run_agent_index
else
  say "Agent graph is fresh. Skipping rebuild."
fi
