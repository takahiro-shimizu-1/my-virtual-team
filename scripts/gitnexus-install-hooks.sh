#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_REPO="${1:-$ROOT}"
HOOK_DIR="$TARGET_REPO/.git/hooks"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"

if [[ ! -d "$HOOK_DIR" ]]; then
  echo "git hooks directory not found: $HOOK_DIR" >&2
  exit 1
fi

backup_hook() {
  local hook_path="$1"
  if [[ -f "$hook_path" && ! -f "${hook_path}.bak" ]]; then
    cp "$hook_path" "${hook_path}.bak"
  elif [[ -f "$hook_path" ]]; then
    cp "$hook_path" "${hook_path}.bak.${TIMESTAMP}"
  fi
}

write_hook() {
  local hook_name="$1"
  local hook_path="$HOOK_DIR/$hook_name"
  backup_hook "$hook_path"
  cat > "$hook_path" <<EOF
#!/bin/bash
set -euo pipefail

if [[ "\${GITNEXUS_AUTO_REINDEX:-1}" == "0" ]]; then
  exit 0
fi

bash "$ROOT/scripts/rebuild-agent-graph.sh" --quiet || true
EOF
  chmod +x "$hook_path"
}

write_hook "post-commit"
write_hook "post-merge"

echo "{\"status\":\"ok\",\"repo\":\"$TARGET_REPO\",\"hooks\":[\"post-commit\",\"post-merge\"]}"
