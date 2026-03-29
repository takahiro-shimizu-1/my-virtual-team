# my-virtual-team Schema

## Agent Frontmatter

すべての `agents/*.md` は以下の frontmatter を持つ。

```yaml
---
agent_id: string
department: string
keywords: [string, ...]
context_refs:
  always: [path, ...]
  on_demand: [path, ...]
  never: [path, ...]
context_budget: number
approval_policy: string
execution_mode: string
---
```

## Generated Registry

### `registry/agents.generated.json`

- agent 一覧
- department
- keywords
- approval_policy
- execution_mode

### `registry/context-policy.generated.json`

- guideline slug -> path / token estimate
- agent -> always / on_demand / never

### `registry/skills.generated.json`

```json
{
  "version": "1.0",
  "generated_at": "ISO-8601",
  "skills": [
    {
      "name": "api-design-review",
      "description": "API設計レビュー向け context pack",
      "file": ".claude/skills/generated/api-design-review.md",
      "keywords": ["API設計レビュー"],
      "agents": ["kirishima-ren", "kujo-haru"],
      "depends_on": ["guidelines/security-policy.md"]
    }
  ]
}
```

## Durable Runtime

Durable state の正本は `.runtime/state.db`。

### `tasks`

主要カラム:

- `task_id`
- `title`
- `description`
- `agent_id`
- `source`
- `workflow_id`
- `idempotency_key`
- `status`
- `priority`
- `task_mode`
- `created_by`
- `claimed_by`
- `payload_json`
- `lock_targets_json`
- `affected_files_json`
- `affected_skills_json`
- `max_attempts`
- `current_attempt`
- `lease_expires_at`
- `last_heartbeat_at`
- `error_message`
- `created_at`
- `updated_at`

### 補助テーブル

- `task_dependencies`
- `task_locks`
- `task_attempts`
- `task_events`
- `task_outputs`
- `task_approvals`
- `skill_runs`
- `skill_health_snapshots`
- `knowledge_diffs`
- `watch_sources`
- `notifications`
- `notification_deliveries`

## Event Flow

1. `task_events` に state transition を記録
2. `.runtime/exports/skill-bus/task-events-YYYY-MM-DD.jsonl` へ mirror export
3. `notifications` / `notification_deliveries` に fan-out 結果を記録

### GitHub Binding

task payload が GitHub issue / PR と紐づく場合は以下を持てる。

```json
{
  "github": {
    "repo": "owner/repo",
    "issue_number": 12,
    "close_on_complete": true
  }
}
```

- `issue_number`: issue comment を送る
- `pr_number`: PR conversation comment を送る
- `close_on_complete`: `task.completed` 時に issue を close する

## Watcher Flow

- `runtime:watch` は watched files の hash を `watch_sources` に保持
- 差分は `knowledge_diffs` に `created / updated / deleted` で追加

## Handoff Schema

```json
{
  "dagId": "wf-20260329-abc",
  "phase": 1,
  "agent": "mizuno-akari",
  "summary": "500字以内の要約",
  "outputs": ["outputs/requirements-spec-20260329.md"],
  "requiredContext": [
    "outputs/requirements-spec-20260329.md",
    "guidelines/company-overview.md"
  ],
  "nextPhase": {
    "agent": "kirishima-ren",
    "task": "要件に基づく技術設計"
  },
  "completedAt": "2026-03-29T10:30:00+09:00"
}
```
