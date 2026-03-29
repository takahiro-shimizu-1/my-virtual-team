#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    ".gitignore",
    "package.json",
    "package-lock.json",
    ".github/workflows/validate.yml",
    ".github/workflows/agent-pr-verify.yml",
    ".github/workflows/github-ops.yml",
    ".github/workflows/native-agent-kickoff.yml",
    ".github/workflows/native-agent-watchdog.yml",
    ".github/workflows/issue-native-plan.yml",
    ".github/workflows/native-agent-review.yml",
    ".github/workflows/auto-merge.yml",
    ".github/workflows/gitnexus-impact.yml",
    ".github/workflows/gitnexus-reindex.yml",
    ".github/workflows/gitnexus-weekly.yml",
    ".github/workflows/runtime-maintenance.yml",
    ".github/agents/vt-implementation-auto.md",
    ".github/agents/vt-implementation-claude.md",
    ".github/agents/vt-implementation-codex.md",
    "README.md",
    "CLAUDE.md",
    "CLAUDE.md.builder",
    ".gitnexus/workspace.json",
    "outputs/.gitkeep",
    "logs/.gitkeep",
    "docs/architecture.md",
    "docs/execution-policy.md",
    "docs/github-ops.md",
    "docs/ai-pipeline.md",
    "docs/integration-gap-recovery.md",
    "docs/runbook.md",
    "docs/schema.md",
    "docs/builder-migration.md",
    "docs/v4-todo.md",
    "scripts/ci-verify.sh",
    "scripts/ensure-v4-ready.sh",
    "scripts/build-registry.js",
    "scripts/github-agent-task.py",
    "scripts/ensure-github-labels.sh",
    "scripts/gitnexus-doctor.sh",
    "scripts/gitnexus-install-hooks.sh",
    "scripts/gitnexus-smoke-test.sh",
    "scripts/github-event-bridge.py",
    "scripts/github-issue.sh",
    "scripts/github-pr-comment.sh",
    "scripts/rebuild-agent-graph.sh",
    "scripts/resolve-agent-context.sh",
    "scripts/runtime-task.sh",
    "runtime/src/gitnexus/agent_graph_builder.py",
    "runtime/src/gitnexus/context_resolver.py",
    "runtime/src/gitnexus/impact_report.py",
    "runtime/src/control/__init__.py",
    "runtime/src/events/__init__.py",
    "runtime/src/health/__init__.py",
    "runtime/src/watchers/__init__.py",
    "registry/agents.generated.json",
    "registry/context-policy.generated.json",
    "registry/skills.generated.json",
    "runtime/migrations/001_initial.sql",
    "runtime/migrations/002_phase3_phase4.sql",
    "runtime/src/control/router.py",
    "runtime/src/control/decomposer.py",
    "runtime/src/control/ai_runner.py",
    "runtime/src/control/execution_policy.py",
    "runtime/src/control/runner_bridge.py",
    "runtime/src/control/codex_runner.py",
    "runtime/src/control/maintenance.py",
    "runtime/src/control/skill_monitor.py",
    "runtime/src/cli/maintenance.py",
    "runtime/src/cli/skill_improve.py",
    "runtime/src/events/bus.py",
    "runtime/src/integrations/github_ops.py",
    "runtime/src/health/aggregate.py",
    "runtime/src/watchers/local_files.py",
    "runtime/tests/test_github_agent_task.py",
    "runtime/tests/test_github_integration.py",
    "runtime/tests/test_runtime.py",
]

REQUIRED_AGENT_KEYS = [
    "agent_id",
    "department",
    "keywords",
    "context_refs",
    "context_budget",
    "approval_policy",
    "execution_mode",
]

ACTIVE_DOCS = [
    "CLAUDE.md",
    "CLAUDE.md.builder",
    ".claude/commands/strategy.md",
    ".claude/commands/development.md",
    ".claude/commands/marketing.md",
    ".claude/commands/research.md",
    ".claude/commands/admin.md",
    ".claude/rules/agent-launch.md",
]

BANNED_PATTERNS = [
    "Agent toolでサブエージェントとして起動してください",
    "必ずAgent toolでサブエージェントを起動し",
    "jq \". += [",
]


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    block = text[4:end]
    data: dict[str, object] = {}
    current_key = ""
    current_map: dict[str, object] | None = None
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if not line.startswith("  "):
            key, _, raw_value = line.partition(":")
            key = key.strip()
            raw_value = raw_value.strip()
            if raw_value:
                data[key] = raw_value
                current_key = ""
                current_map = None
            else:
                data[key] = {}
                current_key = key
                current_map = data[key]  # type: ignore[assignment]
            continue
        if current_key and current_map is not None:
            subkey, _, raw_value = line.strip().partition(":")
            current_map[subkey.strip()] = raw_value.strip()
    return data


def check_required_paths(errors: list[str]) -> None:
    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).exists():
            errors.append(f"missing required path: {relative}")


def check_agents(errors: list[str]) -> None:
    for path in sorted((ROOT / "agents").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        if not frontmatter:
            errors.append(f"agent frontmatter missing: {path.relative_to(ROOT)}")
            continue
        for key in REQUIRED_AGENT_KEYS:
            if key not in frontmatter:
                errors.append(f"agent frontmatter key missing: {path.relative_to(ROOT)} -> {key}")
        body = text
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end != -1:
                body = text[end + 5 :]
        for pattern in ["- `always`:", "- `on_demand`:", "- `never`:"]:
            if pattern in body:
                errors.append(f"agent body duplicates context_refs SSOT: {path.relative_to(ROOT)} -> {pattern}")


def check_registries(errors: list[str]) -> None:
    for relative, key in [
        ("registry/agents.generated.json", "agents"),
        ("registry/context-policy.generated.json", "agents"),
        ("registry/skills.generated.json", "skills"),
    ]:
        data = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        if key not in data:
            errors.append(f"registry missing key: {relative} -> {key}")


def check_active_docs(errors: list[str]) -> None:
    for relative in ACTIVE_DOCS:
        text = (ROOT / relative).read_text(encoding="utf-8")
        for pattern in BANNED_PATTERNS:
            if pattern in text:
                errors.append(f"banned legacy pattern found in {relative}: {pattern}")


def check_pycache(errors: list[str]) -> None:
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    for path in tracked:
        if "__pycache__" in path or path.endswith(".pyc"):
            errors.append(f"tracked cache artifact found: {path}")


def _is_absoluteish(value: str) -> bool:
    return value.startswith("/") or value.startswith("~") or bool(re.match(r"^[A-Za-z]:[\\\\/]", value))


def check_workspace_portability(errors: list[str]) -> None:
    data = json.loads((ROOT / ".gitnexus/workspace.json").read_text(encoding="utf-8"))
    for label, value in [("workspace_root", data.get("workspace_root", ""))]:
        if isinstance(value, str) and _is_absoluteish(value):
            errors.append(f"workspace path must be relative: {label} -> {value}")
    for node in data.get("nodes", []):
        value = node.get("workspace_root", "")
        if isinstance(value, str) and _is_absoluteish(value):
            errors.append(f"workspace path must be relative: nodes[{node.get('id', '?')}].workspace_root -> {value}")


def check_docs_for_absolute_paths(errors: list[str]) -> None:
    targets = [
        ROOT / "docs",
        ROOT / "CLAUDE.md",
        ROOT / "CLAUDE.md.builder",
        ROOT / "DESIGN_CONSTRAINTS.md",
        ROOT / "README.md",
    ]
    for target in targets:
        paths = target.rglob("*.md") if target.is_dir() else [target]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            if "/home/shimizu/" in text:
                errors.append(f"hardcoded absolute path found in markdown: {path.relative_to(ROOT)}")


def main() -> int:
    errors: list[str] = []
    check_required_paths(errors)
    check_agents(errors)
    check_registries(errors)
    check_active_docs(errors)
    check_pycache(errors)
    check_workspace_portability(errors)
    check_docs_for_absolute_paths(errors)

    payload = {
        "status": "ok" if not errors else "error",
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
