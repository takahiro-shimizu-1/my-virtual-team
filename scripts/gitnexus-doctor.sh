#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="$ROOT/.gitnexus/agent-graph.db"
QUERY="${1:-API設計レビュー}"
STATUS_JSON="$(mktemp)"
CONTEXT_JSON="$(mktemp)"
trap 'rm -f "$STATUS_JSON" "$CONTEXT_JSON"' EXIT

if [[ ! -f "$ROOT/.gitnexus/workspace.json" ]]; then
  echo "missing .gitnexus/workspace.json" >&2
  exit 1
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "missing .gitnexus/agent-graph.db" >&2
  echo "run: npm run graph:build" >&2
  exit 1
fi

python3 "$ROOT/runtime/src/gitnexus/agent_graph_builder.py" status "$ROOT" --db "$DB_PATH" --json > "$STATUS_JSON"
VIRTUAL_TEAM_SKIP_ENSURE=1 bash "$ROOT/scripts/resolve-agent-context.sh" "$QUERY" --json > "$CONTEXT_JSON"

python3 - "$STATUS_JSON" "$CONTEXT_JSON" <<'PY'
import json
import pathlib
import sys

status = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
context = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))

errors = []
if status.get("agents", 0) <= 0:
    errors.append("agents_missing")
if status.get("skills", 0) <= 0:
    errors.append("skills_missing")
if status.get("edges", 0) <= 0:
    errors.append("edges_missing")
if not context.get("matched_agents"):
    errors.append("resolver_no_agents")
if not context.get("files_to_read"):
    errors.append("resolver_no_files")

payload = {
    "status": "ok" if not errors else "error",
    "query": context.get("query", ""),
    "graph": {
        "agents": status.get("agents", 0),
        "skills": status.get("skills", 0),
        "knowledge_docs": status.get("knowledge_docs", 0),
        "memory_docs": status.get("memory_docs", 0),
        "edges": status.get("edges", 0),
        "db_path": status.get("db_path", ""),
    },
    "resolver": {
        "matched_agents": context.get("matched_agents", []),
        "matched_skills": context.get("matched_skills", []),
        "files_to_read": context.get("files_to_read", []),
    },
    "errors": errors,
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
sys.exit(0 if not errors else 1)
PY
