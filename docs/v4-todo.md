# v4 TODO

## Phase 0

- [x] `.gitignore` を追加
- [x] `package.json` を追加
- [x] `outputs/.gitkeep` を追加
- [x] `DESIGN_CONSTRAINTS.md` を追加
- [x] `docs/architecture.md` を追加
- [x] `docs/schema.md` を追加
- [x] `docs/runbook.md` を追加
- [x] `guidelines/top-posts-summary.md` を追加
- [x] `guidelines/top-posts-top20.md` を追加
- [x] 全 agent に frontmatter を追加
- [x] 全 agent の context tier を本文にも反映
- [x] `scripts/build-registry.js` を追加
- [x] `AGENTS_CLAUDE.md` 生成を registry build に統合
- [x] `.gitnexus/knowledge/` curated mirror を生成
- [x] registry 生成を実行
- [x] `.claude/rules/agent-launch.md` を更新
- [x] `CLAUDE.md` を更新

## Phase 1

- [x] `.gitnexus/workspace.json` を追加
- [x] `scripts/rebuild-agent-graph.sh` を追加
- [x] `registry/skills.generated.json` を生成
- [x] `npm run graph:build` を通す
- [x] representative task で context resolver を検証

## Phase 2

- [x] durable store schema を実装
- [x] task lifecycle CLI を実装
- [x] JSONL mirror export を追加
- [x] approval / timeout / retry の基本動作を入れる

## Phase 3

- [x] chief を tracked fast path + DAG dispatch 前提に更新
- [x] `runtime/src/control/router.py` を実装
- [x] `runtime/src/control/decomposer.py` を実装
- [x] `runtime/src/control/runner_bridge.py` を実装
- [x] `.claude/commands/*.md` を runtime registration 前提に更新

## Phase 4

- [x] event bus を実装
- [x] Slack / Notion / activity log を adapter 化
- [x] local watcher を実装
- [x] `/health` 相当の集計 CLI を追加

## Phase 5

- [x] `docs/builder-migration.md` を追加
- [x] `CLAUDE.md.builder` に v4 出力契約を追記
- [x] 新規生成に必要な出力物一覧を builder へ明記
- [x] `validate:v4` を追加し builder 完了条件を executable にした

## Validation

- [x] `npm run registry:build`
- [x] `npm run graph:build`
- [x] `npm run runtime:migrate`
- [x] `npm run runtime:test`
- [x] `runtime:task route` で representative routing を確認
- [x] `runtime:task plan --dispatch` で multi-phase workflow を確認
- [x] `runtime:watch`
- [x] `runtime:health`
- [x] `runtime:events`
- [x] `validate:v4`
