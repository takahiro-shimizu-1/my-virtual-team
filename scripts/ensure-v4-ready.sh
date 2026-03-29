#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUIET=0
SKIP_VALIDATE=0
SKIP_GRAPH=0
SKIP_MIGRATE=0
SKIP_REGISTRY=0

for arg in "$@"; do
  case "$arg" in
    --quiet)
      QUIET=1
      ;;
    --skip-validate)
      SKIP_VALIDATE=1
      ;;
    --skip-graph)
      SKIP_GRAPH=1
      ;;
    --skip-migrate)
      SKIP_MIGRATE=1
      ;;
    --skip-registry)
      SKIP_REGISTRY=1
      ;;
  esac
done

say() {
  if [[ "$QUIET" -ne 1 ]]; then
    echo "$@"
  fi
}

run_quiet() {
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

GRAPH_ARGS=()
if [[ "$QUIET" -eq 1 ]]; then
  GRAPH_ARGS+=(--quiet)
fi

cd "$ROOT"

say "Ensuring v4 workspace is ready..."

if [[ "$SKIP_REGISTRY" -ne 1 ]]; then
  if [[ "$QUIET" -eq 1 ]]; then
    run_quiet npm run registry:build
  else
    npm run registry:build
  fi
fi

if [[ "$SKIP_GRAPH" -ne 1 ]]; then
  SKIP_REGISTRY_BUILD=1 bash scripts/rebuild-agent-graph.sh "${GRAPH_ARGS[@]}"
fi

if [[ "$SKIP_MIGRATE" -ne 1 ]]; then
  if [[ "$QUIET" -eq 1 ]]; then
    run_quiet npm run runtime:migrate
  else
    npm run runtime:migrate
  fi
fi

if [[ "$SKIP_VALIDATE" -ne 1 ]]; then
  if [[ "$QUIET" -eq 1 ]]; then
    run_quiet npm run validate:v4
  else
    npm run validate:v4
  fi
fi

say "v4 workspace is ready."
