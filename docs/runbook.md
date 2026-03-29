# my-virtual-team Runbook

## Bootstrap

```bash
npm run bootstrap
```

fresh clone 直後や builder 生成直後はこれを 1 回流せばよい。通常利用では `runtime:task` と `graph:context` が必要な準備を自動で実行する。
GitHub Actions では `.github/workflows/validate.yml` が同じ検証を `npm run ci:verify` で流す。
Issue / PR 運用では `.github/workflows/github-ops.yml` が route / plan の自動応答を返す。

または個別に:

```bash
npm run registry:build
npm run graph:build
npm run runtime:migrate
npm run validate:v4
```

期待結果:

- `registry/agents.generated.json`
- `registry/context-policy.generated.json`
- `registry/skills.generated.json`
- `AGENTS_CLAUDE.md`
- `.gitnexus/knowledge/`
- `.runtime/state.db`
- v4 構成 validation が `ok`

## Chief の基本操作

`runtime:task` は内部で registry build と migrate を自動実行する。`graph:context` は graph freshness を自動で整える。

### 単発 task

```bash
npm run runtime:task -- route --command development --prompt "API設計レビューをお願いします"
npm run runtime:task -- start --command development --prompt "API設計レビューをお願いします" --runner chief
```

### 複数 phase task

```bash
npm run runtime:task -- plan --command strategy --prompt "提案をまとめて、その後要件も整理して" --dispatch
```

### approval

```bash
npm run runtime:task -- approve --task-id task-xxxx --decision approved --note "chief ok"
```

### 実行結果

```bash
npm run runtime:task -- claim --task-id task-xxxx --runner chief
npm run runtime:task -- heartbeat --task-id task-xxxx
npm run runtime:task -- complete --task-id task-xxxx --output outputs/example.md
```

retryable fail:

```bash
npm run runtime:task -- fail --task-id task-xxxx --error "temporary failure" --retryable
```

timeout sweep:

```bash
npm run runtime:task -- sweep
```

## Event / Health / Watch

```bash
npm run runtime:events
npm run runtime:health
npm run runtime:watch
npm run runtime:github-bridge -- handle --event-name issues --event-path event.json --dry-run
npm run ci:verify
npm run validate:v4
```

意味:

- `runtime:events`: `task.completed` などを activity log / Slack / Notion / GitHub へ fan-out し、既定では queue が空になるまで drain する
- `runtime:github-bridge`: GitHub issue / PR event payload を dry run で検証
- `runtime:health`: queue / lock / recent failures / notifications / skill health を集計
- `runtime:watch`: `agents/`, `guidelines/`, `templates/`, `.claude/rules/` の差分を `knowledge_diffs` へ記録
- `ci:verify`: bootstrap + runtime test + representative route/context smoke + clean worktree を一括確認
- `validate:v4`: active docs と runtime 構成が v4 契約を守っているか確認

## GitHub Operations

```bash
./scripts/github-issue.sh github-issue-create --title "調査依頼" --body "API設計レビューをしたい"
./scripts/github-issue.sh github-issue-update --issue-number 12 --label development --body "追加要件あり"
./scripts/github-issue.sh github-issue-close --issue-number 12 --comment "完了"
./scripts/github-issue.sh github-issue-assign --issue-number 12 --assignee copilot-swe-agent
./scripts/github-pr-comment.sh --pr-number 3 --body "route summary を更新しました"
```

`--dry-run` を付けると GitHub へ送信せず payload を確認できる。
詳細は `docs/github-ops.md`。

GitHub-hosted smoke test:

```bash
gh workflow run github-ops.yml --ref <branch> -f scenario=issues -f prompt='API設計レビューをお願いします'
```

## stale graph 対処

以下を変更したら graph rebuild を実行する。

- `agents/**`
- `guidelines/**`
- `templates/**`
- `.claude/rules/**`
- `.claude/commands/**`
- `.claude/skills/**`
- `.gitnexus/workspace.json`

```bash
npm run registry:build
npm run graph:build
```

## Local Integrations

互換ラッパー:

- `./scripts/log-activity.sh`
- `./scripts/slack-notify.sh`
- `./scripts/notion-sync.sh`
- `./scripts/github-issue.sh`
- `./scripts/github-pr-comment.sh`

内部では `runtime/src/cli/integrations.py` を呼び、jq や curl に依存しない。

## 障害時チェック

1. `npm run runtime:health` で queue / failures / notifications を確認
2. `npm run runtime:watch` で knowledge diff が取れているか確認
3. `npm run runtime:events` を流して delivery status を確認
4. `npm run registry:build && npm run graph:build` で graph freshness を戻す
5. 必要なら `outputs/` の handoff と `.runtime/exports/skill-bus/` を監査する
