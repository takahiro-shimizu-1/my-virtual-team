#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT"
BASELINE_STATUS="$(git status --porcelain)"

npm run bootstrap
npm run runtime:test

VIRTUAL_TEAM_SKIP_ENSURE=1 bash scripts/runtime-task.sh route --command development --prompt "API設計レビューをお願いします" > "$TMP_DIR/route-development.json"
python3 - "$TMP_DIR/route-development.json" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["matched_skill"]["name"] == "api-design-review", payload
assert payload["owner"]["agent_id"] in {"kirishima-ren", "kujo-haru"}, payload
PY

VIRTUAL_TEAM_SKIP_ENSURE=1 bash scripts/runtime-task.sh route --command marketing --prompt "X投稿案を作って" > "$TMP_DIR/route-marketing.json"
python3 - "$TMP_DIR/route-marketing.json" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["matched_skill"]["name"] == "x-post-context", payload
assert payload["owner"]["agent_id"] == "asahina-yu", payload
assert payload["approval_required"] is True, payload
PY

VIRTUAL_TEAM_SKIP_ENSURE=1 bash scripts/runtime-task.sh start --command development --prompt "Web APIの実装方針を整理して" --runner ci > "$TMP_DIR/start-development.json"
python3 - "$TMP_DIR/start-development.json" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["status"] == "claimed", payload
assert payload["claimed_task"]["claimed_by"] == "ci", payload
PY

VIRTUAL_TEAM_SKIP_ENSURE=1 bash scripts/runtime-task.sh start --command marketing --prompt "X投稿案を作って" --runner ci > "$TMP_DIR/start-marketing.json"
python3 - "$TMP_DIR/start-marketing.json" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["status"] == "approval_required", payload
assert payload["claimed_task"] is None, payload
PY

VIRTUAL_TEAM_SKIP_ENSURE=1 bash scripts/resolve-agent-context.sh "API設計レビュー" --json > "$TMP_DIR/context-api-review.json"
python3 - "$TMP_DIR/context-api-review.json" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert "api-design-review" in payload["matched_skills"], payload
assert "桐島 蓮" in payload["matched_agents"] or "九条 ハル" in payload["matched_agents"], payload
assert any(path.endswith("api-design-review.md") for path in payload["files_to_read"]), payload
PY

python3 runtime/src/gitnexus/impact_report.py --repo . --db .gitnexus/agent-graph.db --markdown README.md docs/runbook.md > "$TMP_DIR/impact.md"
python3 - "$TMP_DIR/impact.md" <<'PY'
import pathlib
import sys

body = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
assert "## GitNexus Impact Report" in body, body
assert "risk_level" in body, body
PY

VIRTUAL_TEAM_SKIP_ENSURE=1 bash scripts/runtime-task.sh codex --prompt "README.md を整備して quickstart をまとめて" --command admin --target-path README.md --dry-run > "$TMP_DIR/codex-dry-run.json"
python3 - "$TMP_DIR/codex-dry-run.json" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["route"]["owner"]["agent_id"] == "komiya-sakura", payload
assert payload["execution"]["status"] == "dry_run", payload
assert payload["execution"]["output_paths"] == ["README.md"], payload
PY

python3 runtime/src/cli/watch.py scan > "$TMP_DIR/watch.json"
python3 runtime/src/cli/maintenance.py run --days 30 --dry-run > "$TMP_DIR/maintenance.json"
python3 runtime/src/cli/events.py publish > "$TMP_DIR/events.json"
python3 runtime/src/cli/health.py > "$TMP_DIR/health.json"

cat > "$TMP_DIR/github-issue-event.json" <<'JSON'
{
  "repository": {"full_name": "example-org/example-repo"},
  "issue": {
    "number": 11,
    "title": "API設計レビューをお願いします",
    "body": "既存の認証フローを整理してレビューしたいです。"
  }
}
JSON

python3 scripts/github-event-bridge.py handle \
  --event-name issues \
  --event-path "$TMP_DIR/github-issue-event.json" \
  --dry-run > "$TMP_DIR/github-issue-bridge.json"

python3 - "$TMP_DIR/github-issue-bridge.json" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["action"] == "issue_routed", payload
assert payload["comment"]["status"] == "dry_run", payload
PY

cat > "$TMP_DIR/github-issue-comment-event.json" <<'JSON'
{
  "repository": {"full_name": "example-org/example-repo"},
  "issue": {
    "number": 12,
    "title": "提案をまとめて、その後要件も整理して",
    "body": "顧客向け提案から要件整理まで見たいです。"
  },
  "comment": {
    "body": "/vt plan",
    "author_association": "MEMBER"
  },
  "sender": {"login": "octocat"}
}
JSON

python3 scripts/github-event-bridge.py handle \
  --event-name issue_comment \
  --event-path "$TMP_DIR/github-issue-comment-event.json" \
  --dry-run > "$TMP_DIR/github-comment-bridge.json"

python3 - "$TMP_DIR/github-comment-bridge.json" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["action"] == "plan", payload
assert payload["comment"]["status"] == "dry_run", payload
assert payload["plan"]["workflow_name"] == "proposal-to-requirements", payload
PY

python3 - "$TMP_DIR/health.json" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert "status_counts" in payload, payload
assert "knowledge_diffs" in payload, payload
PY

python3 - "$TMP_DIR/maintenance.json" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["status"] == "ok", payload
assert "self_improve" in payload, payload
assert "knowledge_review" in payload, payload
PY

FINAL_STATUS="$(git status --porcelain)"

if [[ "$FINAL_STATUS" != "$BASELINE_STATUS" ]]; then
  echo "Repository changed during ci:verify" >&2
  printf '%s\n' "$FINAL_STATUS" >&2
  exit 1
fi
