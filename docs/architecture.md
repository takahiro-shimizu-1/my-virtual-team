# my-virtual-team Architecture

## Goal

`my-virtual-team` を、静的なプロンプト集から、知識・状態・実行・運用を分離したマルチエージェント基盤へ移行する。

## 4 Plane

### Knowledge Plane

- `agents/*.md`
- `guidelines/`
- `templates/`
- `.gitnexus/workspace.json`
- GitNexus Agent Context Graph

役割:

- agent / skill / document / data の関係解決
- task に必要な最小コンテキストの抽出

### Control Plane

- durable task state
- dependency resolution
- lock management
- retry / approval

役割:

- すべての task の登録
- 並列実行制御
- state transition の追跡

### Execution Plane

- chief
- sub-agent launch rules
- runner bridge

役割:

- task claim
- context loading
- output 生成
- handoff 出力

### Operations Plane

- activity logging
- Slack / Notion integration
- health aggregation
- local file watcher

役割:

- 通知
- 監視
- 障害時の状況把握

## SSOT

| Domain | Source |
|---|---|
| agent metadata | `agents/*.md` frontmatter |
| agent persona / behavior | `agents/*.md` 本文 |
| workspace topology | `.gitnexus/workspace.json` |
| task state | durable store |
| outputs | `outputs/` |
| generated registry | `registry/*.generated.json` |

## Phase 0 Scope

Phase 0 では以下だけを先に固める。

- context tier の導入
- top-posts の分割資産化
- frontmatter を使った metadata SSOT 化
- registry 自動生成
- outputs / handoff の標準化

Phase 0 ではまだ durable store や task runtime は実装しない。

## Non-Goals

- OpenClaw 本番連携
- GitHub pipeline 自動化
- 外部 trend watcher
- JSONL を primary runtime にすること
