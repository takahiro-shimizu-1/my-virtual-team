# my-virtual-team v4 完全実装計画

**作成日**: 2026-03-29  
**位置づけ**: [`v3-plan.md`](v3-plan.md) と [`v3-revised.md`](v3-revised.md) を統合し、過剰設計を削り、実装順序・SSOT・永続化・運用まで一本化した最終版

---

## 1. 結論

`my-virtual-team` をスケールさせるために必要なのは、プロンプトやルーターを増やすことではなく、
**知識・状態・実行・運用を分離した基盤に再設計すること**です。

v4 では以下を最終決定とします。

1. **全タスクを control plane に登録する**
   - 単発タスクも例外ではない
   - 「直接起動」は高速実行モードであり、状態管理をスキップしない

2. **状態は Phase 2 で SQLite に載せる**
   - JSONL は互換 export と監査用に限定する
   - JSONL を本番 SSOT にしない

3. **metadata の SSOT は frontmatter に一本化する**
   - `agents/*.md` の frontmatter が正
   - `registry/*.json` は生成物にする

4. **GitNexus は Phase 1 で導入し、freshness を運用に組み込む**
   - context graph は stale のまま使わない

5. **line-harness-oss からは運用パターンだけを取り込む**
   - event bus、health、runbook、migration 形式は採用
   - GitHub/Copilot 固有パイプラインや LINE CRM 固有部分は採用しない

6. **builder 更新は最後だが必須**
   - 新規生成時から v4 構成を出せる状態を完成条件に含める

---

## 2. v4 が解決する前版の問題

### v3 / v3-revised の良かった点

- context tier による即効のトークン削減
- GitNexus Agent Context Graph を基盤に置いたこと
- `agent-skill-bus` の queue / DAG / lock / self-improving loop を取り込もうとしたこと
- `line-harness-oss` の event bus / health / ops を運用設計に使おうとしたこと

### v4 で修正する点

1. **JSONL 主体の期間が長すぎた**
   - v4 では Phase 2 で durable store を入れる

2. **単発タスクが control plane を素通りしていた**
   - v4 では全タスクを task registration する

3. **SSOT が多重だった**
   - v4 では frontmatter + workspace.json + DB の3系統だけに絞る

4. **GitNexus stale 対策がなかった**
   - v4 では freshness check を標準フローに組み込む

5. **導入方法が曖昧だった**
   - v4 では `package.json` と `.gitignore` から始める

6. **不要な取り込みが混じっていた**
   - GitHub/Copilot pipeline、手書き registry、プレースホルダー README などを削る

---

## 3. 最終アーキテクチャ

## 3.1 4 Plane モデル

```text
User / Cron / Webhook / Watcher / Manual Trigger
                    |
                    v
            ┌──────────────────┐
            │  Control Plane   │
            │ task / DAG / lock│
            │ retry / approval │
            └────────┬─────────┘
                     |
       ┌─────────────┼─────────────┐
       v             v             v
   Dispatch      Event Bus     Health/Watchdog
                     |
                     v
              Slack / Notion / Activity Log
                     |
                     v
            Runner Adapters
       (Claude Code / Codex / Human)
                     |
                     v
                outputs/ + runs
                     ^
                     |
            ┌──────────────────┐
            │ Knowledge Plane  │
            │ GitNexus Agent   │
            │ Context Graph    │
            └──────────────────┘
```

## 3.2 Plane ごとの責務

| Plane | 主責務 | 実装元 |
|---|---|---|
| Knowledge Plane | agent/skill/doc/data の関係解決、必要最小コンテキスト取得 | `gitnexus-stable-ops` |
| Control Plane | task 登録、依存解決、lock、retry、approval、event 発火 | `agent-skill-bus` を DB 化 |
| Execution Plane | runner が task を claim して実行し、output / run を返す | `my-virtual-team` 本体 |
| Operations Plane | health、watcher、通知、cleanup、runbook、定期実行 | `line-harness-oss` の運用パターン |

---

## 4. v4 の最終決定事項

## 4.1 SSOT 一覧

| 対象 | SSOT | 備考 |
|---|---|---|
| agent の人格・業務説明 | `agents/*.md` 本文 | 人間向け知識 |
| agent metadata / context tier / keywords | `agents/*.md` frontmatter | 機械可読の正本 |
| guideline / template の実体 | `guidelines/` `templates/` | 人間向け知識 |
| workspace topology | `.gitnexus/workspace.json` | GitNexus の正本 |
| task / lock / event / runs / health | `.runtime/state.db` | Durable state |
| 成果物 | `outputs/` | 人間と次フェーズ用 |
| registry JSON | `registry/*.generated.json` | 生成物。手編集しない |
| legacy JSONL / markdown history | `.runtime/exports/skill-bus/` | 互換 / 監査専用 |

## 4.2 生成物の扱い

以下は **手書きしない**。

- `registry/agents.generated.json`
- `registry/context-policy.generated.json`
- `registry/skills.generated.json`
- `AGENTS.md`（必要なら生成）

### 理由

`agents/*.md` と registry JSON の二重管理を避けるため。  
frontmatter を直せば registry を再生成できる構成にする。

## 4.3 全タスク登録ルール

すべてのタスクは最初に task table に登録する。

- 単発タスク:
  - `create -> claim -> execute -> complete` を同一プロセスで即時実行
- 複数エージェントタスク:
  - `create -> decompose -> dependencies -> dispatch`
- 定期タスク:
  - cron / watcher が create
- 外部イベント:
  - webhook / integration adapter が create

つまり「直接起動」は存在してよいが、**状態管理をバイパスしない**。

## 4.4 永続化ルール

- Phase 2 から `.runtime/state.db` を導入する
- JSONL は DB の state transition から export する
- `bus/` を primary store として新設しない

## 4.5 GitNexus freshness ルール

以下の変更があったら agent graph を再構築対象とする。

- `agents/**`
- `guidelines/**`
- `templates/**`
- `.claude/rules/**`
- `.claude/commands/**`
- `.claude/skills/**`
- `.gitnexus/workspace.json`

実行ポリシー:

1. タスク開始前に freshness を確認
2. stale なら `gni agent-index .` または reindex script を実行
3. fresh な graph に対してのみ `gni agent-context` を使う

## 4.6 初期統合スコープ

v4 の完成条件に含める integration は以下のみ。

- Slack
- Notion
- Activity Log

以下は **将来拡張** とし、v4 完成条件から外す。

- GitHub issue / PR 自動起票
- LINE 通知
- OpenClaw 本番連携
- 外部 community / RSS / competitor trend watcher

---

## 5. やらないこと

1. `agent-skill-bus` の JSONL runtime をそのまま本番採用しない
2. 手書きの `registry/*.json` を作らない
3. `AGENTS.md` を手で保守しない
4. `line-harness-oss/CLAUDE.md` の GitHub/Copilot pipeline を移植しない
5. `runtime/adapters/README.md` のような説明だけのファイルを先に作らない
6. 外部 web watcher を最初から広げない
7. `docx` の原本移行を v4 の前提条件にしない

---

## 6. 目標ディレクトリ構成

```text
my-virtual-team/
├── .gitignore
├── package.json
├── package-lock.json
├── CLAUDE.md
├── CLAUDE.md.builder
├── agents/
├── guidelines/
├── templates/
├── data/
├── outputs/
│   └── .gitkeep
├── docs/
│   ├── v2-plan.md
│   ├── v3-plan.md
│   ├── v3-revised.md
│   ├── v4-plan.md
│   ├── architecture.md
│   ├── runbook.md
│   ├── schema.md
│   └── builder-migration.md
├── .gitnexus/
│   ├── workspace.json
│   └── agent-graph.db
├── registry/
│   ├── agents.generated.json
│   ├── context-policy.generated.json
│   └── skills.generated.json
├── runtime/
│   ├── migrations/
│   │   └── 001_initial.sql
│   ├── src/
│   │   ├── registry/
│   │   ├── graph/
│   │   ├── db/
│   │   ├── control/
│   │   ├── events/
│   │   ├── integrations/
│   │   ├── health/
│   │   ├── watchers/
│   │   └── cli/
│   └── tests/
├── scripts/
│   ├── collect-top-posts.js
│   ├── build-registry.js
│   ├── rebuild-agent-graph.sh
│   ├── runtime-task.sh
│   ├── log-activity.sh
│   ├── slack-notify.sh
│   └── notion-sync.sh
└── .runtime/
    ├── state.db
    └── exports/
        └── skill-bus/
            ├── prompt-request-queue.jsonl
            ├── active-locks.jsonl
            ├── dag-state.jsonl
            ├── skill-runs.jsonl
            ├── skill-health.json
            ├── knowledge-state.json
            ├── knowledge-diffs.jsonl
            └── prompt-request-history.md
```

### 補足

- `runtime/` はコード
- `.runtime/` は可変状態
- `registry/` は生成物
- `outputs/` は成果物

---

## 7. 初期ブートストラップ

この repo は現時点で `package.json` も `.gitignore` もないため、v4 はここから始める。

## 7.1 `.gitignore`

最低限、以下を ignore する。

```gitignore
node_modules/
.runtime/
.gitnexus/agent-graph.db
outputs/tmp/
dist/
```

## 7.2 `package.json`

v4 では root に `package.json` を置き、runtime CLI と運用スクリプトを統一する。

想定スクリプト:

```json
{
  "scripts": {
    "registry:build": "node scripts/build-registry.js",
    "graph:build": "bash scripts/rebuild-agent-graph.sh",
    "db:migrate": "node runtime/src/cli/migrate.js",
    "task:enqueue": "node runtime/src/cli/task.js enqueue",
    "task:dispatch": "node runtime/src/cli/task.js dispatch",
    "health": "node runtime/src/cli/health.js",
    "watch": "node runtime/src/cli/watch.js"
  }
}
```

### 理由

- 導入方法を builder で再現しやすい
- `npx agent-skill-bus` 依存だけにせず、自前 runtime と共存できる
- 運用コマンドを root から統一できる

---

## 8. データモデル

## 8.1 Task 系テーブル

- `tasks`
- `task_dependencies`
- `task_locks`
- `task_attempts`
- `task_events`
- `task_outputs`
- `task_approvals`

### `tasks` の必須カラム

- `id`
- `source`
- `priority`
- `agent_id`
- `task`
- `context`
- `affected_files`
- `affected_skills`
- `status`
- `dag_id`
- `idempotency_key`
- `runner_id`
- `heartbeat_at`
- `retry_count`
- `max_retries`
- `created_at`
- `updated_at`

## 8.2 Quality / Watcher 系テーブル

- `skill_runs`
- `skill_health_snapshots`
- `knowledge_diffs`
- `watch_sources`

## 8.3 Integration 系テーブル

- `notifications`
- `notification_deliveries`

## 8.4 JSONL export

DB から以下を export する。

- `prompt-request-queue.jsonl`
- `active-locks.jsonl`
- `dag-state.jsonl`
- `skill-runs.jsonl`
- `skill-health.json`
- `knowledge-state.json`
- `knowledge-diffs.jsonl`
- `prompt-request-history.md`

つまり JSONL は **出力結果** であり、**入力面の正本ではない**。

---

## 9. 実装フェーズ

### Phase 0: 即効改善 + SSOT 固定

**目的**: 今日から効くトークン削減を入れつつ、今後の正本を固定する

#### 新規作成

- `.gitignore`
- `package.json`
- `outputs/.gitkeep`
- `guidelines/top-posts-summary.md`
- `guidelines/top-posts-top20.md`
- `docs/architecture.md`
- `docs/runbook.md`
- `docs/schema.md`
- `DESIGN_CONSTRAINTS.md`
- `scripts/build-registry.js`

#### 変更

- `agents/**/*.md`
  - frontmatter 追加
  - `context_refs.always/on_demand/never`
  - `agent_id`, `keywords`, `approval_policy`, `execution_mode`
- `.claude/rules/agent-launch.md`
- `.claude/rules/context-reset.md`
- `.claude/rules/reporting-format.md`
- `CLAUDE.md`

#### frontmatter 例

```yaml
---
agent_id: asahina-yu
department: 03-marketing
keywords: [SNS投稿, X運用, コンテンツ企画, 発信]
context_refs:
  always:
    - guidelines/company-overview.md
    - guidelines/output-standards.md
    - guidelines/brand-guidelines.md
  on_demand:
    - guidelines/philosophy.md
    - guidelines/top-posts-summary.md
    - guidelines/top-posts-top20.md
  never:
    - guidelines/security-policy.md
    - guidelines/escalation-rules.md
context_budget: 3000
approval_policy: external_brand_risk
execution_mode: tracked_fast_path
---
```

#### この Phase で決めること

- frontmatter が agent metadata の SSOT
- registry JSON は `scripts/build-registry.js` で生成
- `top-posts-reference.md` は deep analysis 専用

#### 完了条件

- 朝比奈ユウの起動時常時読込が summary/top20 を除いた最小構成に落ちる
- `registry/agents.generated.json` と `registry/context-policy.generated.json` が生成できる
- `.gitignore` と `package.json` が存在する

---

### Phase 1: Knowledge Plane 導入

**目的**: GitNexus Agent Context Graph を最小コンテキスト取得の正規ルートにする

#### 新規作成

- `.gitnexus/workspace.json`
- `scripts/rebuild-agent-graph.sh`
- `registry/skills.generated.json` の生成処理

#### 変更

- `CLAUDE.md`
  - context loading protocol を追加
- 必要に応じて `agents/**/*.md` frontmatter を微修正

#### workspace.json の方針

- `nodes` は最小で1つ
- `services` は最初は `chief`, `gitnexus`, `runtime` のみ
- `knowledge_refs` は `guidelines`, `.claude/skills`, `docs`, `templates`

#### freshness 対応

`scripts/rebuild-agent-graph.sh` は以下を担う。

1. 変更対象を確認
2. stale なら `gni agent-index .`
3. 成功時のみ context resolver を使える状態にする

#### 完了条件

- `gni agent-index .` が通る
- `gni agent-context "X投稿を作成して"` で朝比奈ユウ周辺だけ返る
- `gni agent-context "API設計レビュー"` で開発系だけ返る
- stale graph のまま context resolver を使わない運用が決まる

---

### Phase 2: Durable Control Plane 実装

**目的**: queue / DAG / lock / retry を durable state に移す

#### 新規作成

- `runtime/migrations/001_initial.sql`
- `runtime/src/db/*`
- `runtime/src/control/*`
- `runtime/src/cli/task.js`
- `runtime/src/cli/migrate.js`
- `scripts/runtime-task.sh`

#### 変更

- `CLAUDE.md`
- `.claude/rules/agent-launch.md`
- 必要なら各 `.claude/commands/*.md`

#### 実装方針

- すべての task は DB に `create`
- 単発 task は `tracked_fast_path`
  - DB登録後、同一プロセスで即時 claim / execute
- 複数 task は DAG 分解
- file lock は DB で管理
- state transition ごとに JSONL mirror を export

#### この Phase で完成させる CLI

- `task create`
- `task claim`
- `task heartbeat`
- `task complete`
- `task fail`
- `task dispatch`

#### 完了条件

- runner 再起動後も状態が維持される
- lock timeout / retry が動く
- 単発 task も DB に記録される
- JSONL mirror が `.runtime/exports/skill-bus/` に出力される

---

### Phase 3: Chief 縮小 + Runner 統合

**目的**: chief を policy / approval / synthesis に縮小し、実行は control plane に寄せる

#### 新規作成

- `runtime/src/control/router.js`
- `runtime/src/control/decomposer.js`
- `runtime/src/control/runner-bridge.js`

#### 変更

- `CLAUDE.md`
- `.claude/commands/*.md`

#### 決定事項

- `/strategy` など既存コマンドは残す
- ただし内部では task registration を通す
- chief の役割は以下のみ
  - 意図の明確化
  - high-risk approval
  - 複数結果の統合

#### v4 core で対応する runner

- local Claude/Codex runner
- human/manual runner

#### v4 core から外すもの

- OpenClaw 本番 adapter
- GitHub Actions runner

#### 完了条件

- 複数エージェントタスクが chief の手動中継なしで進む
- `/strategy` などの表面仕様は維持される
- chief が毎回全文コンテキストを読まない

---

### Phase 4: Event Bus + Observability + Self-Improvement

**目的**: 通知・健康診断・劣化検知を event-driven にする

#### 新規作成

- `runtime/src/events/bus.js`
- `runtime/src/integrations/slack.js`
- `runtime/src/integrations/notion.js`
- `runtime/src/health/aggregate.js`
- `runtime/src/watchers/local-files.js`
- `runtime/src/cli/health.js`

#### 変更

- `scripts/log-activity.sh`
- `scripts/slack-notify.sh`
- `scripts/notion-sync.sh`
- `.claude/skills/review/SKILL.md`
- 必要なら `.claude/rules/skill-logging.md`

#### event bus の初期対象イベント

- `task.created`
- `task.completed`
- `task.failed`
- `task.timeout`
- `skill.degraded`
- `approval.requested`

#### 初期 watcher の対象

- `agents/**`
- `guidelines/**`
- `templates/**`
- `.claude/rules/**`

#### 注意

この Phase の watcher は **ローカル資産の変更検知** に限定する。  
外部 RSS / trend / competitor 監視は v4 完了条件に含めない。

#### 完了条件

- task 完了で activity log / Slack / Notion が event bus 経由で動く
- `skill_runs` と `skill_health_snapshots` が更新される
- `/health` で queue / run / lock / health を確認できる
- `guidelines/` の更新が `knowledge_diffs` に残る

---

### Phase 5: Builder 更新 + 仕上げ

**目的**: 新規生成時から v4 を出せるようにする

#### 新規作成

- `docs/builder-migration.md`

#### 変更

- `CLAUDE.md.builder`
- 必要なら setup/usage ドキュメント

#### builder が生成すべきもの

- `.gitignore`
- `package.json`
- `outputs/`
- `.gitnexus/workspace.json`
- `runtime/`
- `.runtime/` 用初期化処理
- frontmatter 入り agent 定義
- registry 生成 script

#### 完了条件

- 新規生成チームが v4 構成で立ち上がる
- 手作業なしで registry build / graph build / db migrate ができる

---

## 10. フェーズごとの不要物整理

| 段階 | 作らないもの | 理由 |
|---|---|---|
| Phase 0 | 手書き `registry/agents.json` | frontmatter と二重管理になる |
| Phase 0 | `AGENTS.md` 手書き版 | 必要なら後で生成すればよい |
| Phase 1 | 外部 trend watcher | まだ過剰 |
| Phase 2 | JSONL primary store | 根本課題が残る |
| Phase 3 | OpenClaw adapter | この repo 単体の完成条件ではない |
| Phase 4 | GitHub/LINE adapter | 現在の必須 integration ではない |
| 全体 | 説明だけの placeholder README | 実装に寄与しない |

---

## 11. 検証計画

| Phase | テスト | 成功条件 |
|---|---|---|
| 0 | 朝比奈ユウの起動 | 常時読込が最小化される |
| 0 | registry build | frontmatter から生成できる |
| 1 | `gni agent-context` 代表10タスク | 5,000 tokens 以内で妥当な file が返る |
| 1 | stale graph 検知 | fresh でない状態を検出できる |
| 2 | 単発 task 実行 | DB に create/claim/complete が残る |
| 2 | 2 worker 並列実行 | lock が効く |
| 2 | DAG 実行 | dependsOn が正しく解決される |
| 3 | 複数エージェント連携 | chief を中継役にせず進む |
| 4 | task.completed イベント | Slack / Notion / activity log に fan-out する |
| 4 | skill health 集計 | 劣化 task を可視化できる |
| 5 | builder 実行 | v4 構成が自動生成される |

---

## 12. 移行安全性

### 原則

- 既存の `/strategy` `/development` `/marketing` `/research` `/admin` は維持
- 既存の `agents/`, `guidelines/`, `templates/` は壊さない
- 既存 shell script は一旦残し、内部を runtime 呼び出しへ置換する

### ロールバック単位

| Phase | ロールバック |
|---|---|
| 0 | frontmatter 追加分と script を戻す |
| 1 | `.gitnexus/` と graph build フローを外す |
| 2 | `runtime/` と `.runtime/state.db` を外し旧運用へ戻す |
| 3 | `CLAUDE.md` を Phase 2 版に戻す |
| 4 | event bus と integrations を切る |
| 5 | builder だけを旧版へ戻す |

---

## 13. Definition of Done

1. 全エージェントが frontmatter ベースの context tier で最小トークン起動する
2. GitNexus Agent Context Graph で task に応じた file 解決ができる
3. すべての task が control plane に登録される
4. task / lock / event / run / health が SQLite に永続化される
5. JSONL は export として出力されるが SSOT ではない
6. chief は policy / approval / synthesis に縮小される
7. Slack / Notion / activity log が event-driven で動く
8. local watcher で knowledge diff を検知できる
9. runbook と `/health` だけで障害時の状況把握ができる
10. builder が v4 構成を生成できる

---

## 14. 最初の2週間の着手順

### Week 1

- `.gitignore` 作成
- `package.json` 作成
- `top-posts-summary.md` / `top-posts-top20.md` 作成
- `agents/*.md` に frontmatter 追加
- `scripts/build-registry.js` 作成
- `CLAUDE.md` / `agent-launch.md` / `context-reset.md` 更新

### Week 2

- `.gitnexus/workspace.json` 作成
- `scripts/rebuild-agent-graph.sh` 作成
- `gni agent-index .` を通す
- `runtime/migrations/001_initial.sql` 作成
- task CLI の最小実装
- 単発 task も DB 登録に通す

この 2 週間で、
「人格付き Markdown 集」から
「Knowledge Plane + Durable Control Plane を持つ基盤」
へ変わり始める。

---

## 15. 最終判断

v4 では、`my-virtual-team` を

- static prompt kit
- chief 依存の手作業 orchestrator
- JSONL 中心の仮運用

から卒業させます。

目指すのは、

- **frontmatter を正本にした知識管理**
- **GitNexus による最小コンテキスト取得**
- **SQLite による durable task runtime**
- **event-driven な通知と観測**
- **builder まで含む再現可能な構成**

です。

これが、現状資産を活かしながら `agent-skill-bus`、`gitnexus-stable-ops`、`line-harness-oss` を
最も無理なく統合できる、`my-virtual-team` の完成形です。
