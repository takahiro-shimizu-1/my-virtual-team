# my-virtual-team Architecture

## Goal

`my-virtual-team` を、静的な prompt 集ではなく、Knowledge Plane / Control Plane / Execution Plane / Operations Plane を分離したマルチエージェント基盤として運用する。

## 4 Plane

### Knowledge Plane

- `agents/*.md`
- `guidelines/`
- `templates/`
- `.gitnexus/workspace.json`
- `registry/*.generated.json`
- GitNexus Agent Context Graph

責務:

- agent / skill / document の関係解決
- required context の最小抽出
- stale graph の検知と rebuild

### Control Plane

- `.runtime/state.db`
- `runtime/src/control/*`
- `runtime/src/db/*`

責務:

- 全 task の登録
- DAG / dependency 解決
- lock / retry / timeout / approval
- event 発火と JSONL mirror export

### Execution Plane

- `CLAUDE.md`
- `.claude/commands/*.md`
- `.claude/rules/*.md`
- `runtime/src/control/runner_bridge.py`

責務:

- owner / collaborator の routing
- tracked fast path と multi-phase workflow の分岐
- required_context に絞った起動
- outputs / handoff の生成

### Operations Plane

- `runtime/src/events/*`
- `runtime/src/integrations/*`
- `runtime/src/health/*`
- `runtime/src/watchers/*`
- `scripts/log-activity.sh`
- `scripts/slack-notify.sh`
- `scripts/notion-sync.sh`

責務:

- activity log / Slack / Notion への fan-out
- queue / lock / failure / skill health の集計
- local asset diff の検知

## SSOT

| Domain | Source |
|---|---|
| agent metadata | `agents/*.md` frontmatter |
| agent persona / behavior | `agents/*.md` 本文 |
| workspace topology | `.gitnexus/workspace.json` |
| task / lock / event / approval / health | `.runtime/state.db` |
| outputs / handoff | `outputs/` |
| generated registry | `registry/*.generated.json` |

## Core Flow

1. chief が `route` で owner / collaborator / required_context を決める
2. `start` か `plan --dispatch` で task を DB に登録する
3. approval pending があれば chief が判断する
4. runner が claim して実行し、`complete` / `fail` / `timeout` を記録する
5. event bus が activity log / Slack / Notion へ fan-out する
6. `/health` と watcher で queue / skill / knowledge diff を観測する

## Non-Goals

- OpenClaw 本番連携
- GitHub / LINE adapter
- 外部 RSS / competitor watcher
- JSONL を primary runtime に戻すこと
