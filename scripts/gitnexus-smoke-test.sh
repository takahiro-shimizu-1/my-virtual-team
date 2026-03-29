#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUERY="${1:-API設計レビュー}"

cd "$ROOT"

npm run registry:build >/dev/null
bash scripts/rebuild-agent-graph.sh --quiet
python3 runtime/src/gitnexus/agent_graph_builder.py status "$ROOT" --json >/dev/null
VIRTUAL_TEAM_SKIP_ENSURE=1 bash scripts/resolve-agent-context.sh "$QUERY" --json >/dev/null
bash scripts/gitnexus-doctor.sh "$QUERY" >/dev/null

echo "{\"status\":\"ok\",\"query\":\"$QUERY\"}"
