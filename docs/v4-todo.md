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
- [x] `.claude/rules/agent-launch.md` を v4 Phase 0 に更新
- [x] `.claude/rules/context-reset.md` を更新
- [x] `.claude/rules/reporting-format.md` を更新
- [x] `CLAUDE.md` を v4 移行状態に更新

## Phase 1

- [x] `.gitnexus/workspace.json` を追加
- [x] `scripts/rebuild-agent-graph.sh` を追加
- [x] `npm run graph:build` を通す
- [x] representative task で context resolver を検証し ranking を調整する

## Phase 1 Notes

- `docs/phase1-findings.md` に互換ブリッジと ranking 課題を記録
- `scripts/resolve-agent-context.sh` は既定で `--depth 1` を使い、common guideline 経由のノイズを抑える

## Phase 2

- [x] durable store の schema を作成
- [x] task lifecycle CLI を実装
- [x] JSONL export を追加

## Phase 2 Notes

- `.runtime/state.db` を SSOT とし、`task-events-YYYY-MM-DD.jsonl` を mirror 出力
- `create`, `dispatch`, `claim`, `heartbeat`, `complete`, `fail`, `show` を CLI で操作可能
- lock contention と retryable fail を代表ケースで確認済み

## Phase 3

- [ ] chief を tracked fast path + DAG dispatch 前提に更新
- [ ] runner bridge を実装

## Phase 4

- [ ] event bus を実装
- [ ] Slack / Notion / activity log を adapter 化
- [ ] local watcher を実装

## Phase 5

- [ ] `CLAUDE.md.builder` を v4 対応
- [ ] 新規生成チームで v4 構成を検証
