# my-virtual-team Runbook

## Phase 0 Startup

### 1. Registry を再生成する

```bash
npm run registry:build
```

期待結果:

- `registry/agents.generated.json`
- `registry/context-policy.generated.json`
- `AGENTS_CLAUDE.md`
- `.gitnexus/knowledge/`

### 2. Graph を再構築する

```bash
npm run graph:build
```

期待結果:

- `.gitnexus/agent-graph.db` が fresh な状態で更新される
- `gni` ラッパーが壊れている環境でも sibling `gitnexus-stable-ops` から build できる

## 日次確認

- `agents/*.md` frontmatter と本文が矛盾していないか
- `registry/*.generated.json` を再生成して差分が妥当か
- `guidelines/top-posts-summary.md` / `top-posts-top20.md` が最新の reference と整合しているか
- `outputs/` に handoff が残っているか

## stale graph の対処

以下の変更後は graph rebuild を行う。

- `agents/**`
- `guidelines/**`
- `.claude/rules/**`
- `.claude/commands/**`
- `.claude/skills/**`
- `.gitnexus/workspace.json`

### 手順

```bash
npm run registry:build
npm run graph:build
```

## handoff 運用

- フェーズを跨ぐ task は `outputs/handoff-*.json` を出力する
- 次フェーズは `requiredContext` のみ読む
- handoff がない大型タスクは unfinished 扱いにする

## 障害時の最低確認

1. `registry/*.generated.json` を再生成したか
2. `AGENTS_CLAUDE.md` が frontmatter から再生成されているか
3. `.gitnexus/knowledge/` が更新されているか
4. graph が stale でないか
5. `outputs/` に前段成果物があるか
6. `.claude/rules/agent-launch.md` と frontmatter が一致しているか

## 現時点の制約

- durable store 未導入
- event bus 未導入
- health aggregation 未導入
- `gni` のグローバルラッパーはローカル環境差異で壊れることがあるため、repo-local script を優先する
- `scripts/resolve-agent-context.sh` は common guideline 経由のノイズを減らすため、既定で `--depth 1` を使う

そのため Phase 0-1 では、まず context と registry の整合性を最優先で確認する。
