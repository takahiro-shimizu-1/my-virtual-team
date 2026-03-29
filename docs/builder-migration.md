# Builder Migration

## 目的

`CLAUDE.md.builder` が生成するチームを v4 アーキテクチャに揃える。

## builder が必ず生成するもの

- `.gitignore`
- `package.json`
- `outputs/.gitkeep`
- `logs/.gitkeep`
- `.gitnexus/workspace.json`
- `runtime/migrations/`
- `runtime/src/db/`
- `runtime/src/control/`
- `runtime/src/events/`
- `runtime/src/integrations/`
- `runtime/src/health/`
- `runtime/src/watchers/`
- `scripts/build-registry.js`
- `scripts/ensure-v4-ready.sh`
- `scripts/rebuild-agent-graph.sh`
- `scripts/resolve-agent-context.sh`
- `scripts/runtime-task.sh`
- `scripts/log-activity.sh`
- `scripts/slack-notify.sh`
- `scripts/notion-sync.sh`
- frontmatter 入り `agents/*.md`

## builder が守る契約

1. agent metadata の SSOT は `agents/*.md` frontmatter
2. generated registry は手書きしない
3. すべての task は control plane に登録する
4. shell wrapper は runtime CLI の互換ラッパーとして生成する
5. builder 完了時に以下を実行できる状態にする

```bash
npm run bootstrap
npm run registry:build
npm run graph:build
npm run runtime:migrate
npm run runtime:test
npm run runtime:watch
npm run runtime:health
npm run validate:v4
```

## builder の変更点

### 旧版

- Agent tool 直起動
- shell script 個別実装
- JSONL / log 中心
- builder 完了時に runtime 検証がない

### v4

- `route / plan / start / approve` 前提
- SQLite durable store
- event-driven integrations
- watcher / health / graph freshness まで含めて完成
- `runtime:task` と `graph:context` は通常利用で self-healing に動く
- `validate:v4` で構成検証できる
