# my-virtual-team v3 統合再設計計画

**作成日**: 2026-03-29  
**対象**: `my-virtual-team` を、`agent-skill-bus`、`gitnexus-stable-ops`、`line-harness-oss` の強みを統合した、自律稼働・安定運用・スケール可能なマルチエージェント基盤へ再設計する

## 1. 結論

`my-virtual-team` の本質的な問題は、プロンプト資産はあるのに、**ランタイムが存在しない**ことです。  
現状は「人格付き Markdown をチーフが都度読む」設計であり、以下が欠けています。

- 永続的なタスク状態管理
- 依存関係つき並列実行
- コンテキストの段階的解決
- 実行ログと品質フィードバック
- ヘルス監視、再試行、タイムアウト、通知
- 外部イベントからの自律起動

そのため v3 では、単なる `CLAUDE.md` 改良ではなく、以下の 4 層に分離します。

1. **Knowledge Plane**: GitNexus Agent Context Graph を使った最小コンテキスト解決
2. **Control Plane**: Prompt Request Bus を DB 化したタスク制御基盤
3. **Execution Plane**: Claude Code / Codex / OpenClaw / cron / webhook からタスクを処理する runner 群
4. **Operations Plane**: line-harness-oss 型の event bus、health、通知、定期実行、監査

重要なのは、`agent-skill-bus` を「JSONL ファイル群として雑に追加する」のではなく、  
**タスクモデルだけ取り込み、line-harness-oss 型の durable runtime に載せ替える**ことです。

---

## 2. なぜ v2-plan では足りないか

既存の [`v2-plan.md`](v2-plan.md) は方向性の一部は正しいものの、症状への対処に留まっています。

### v2 の良い点

- トークン消費の多さを問題として認識している
- ハンドオフ、DAG、lock の必要性に気づいている
- self-improving loop の必要性を認識している

### v2 の決定的な不足

1. **制御面がファイル追加前提のまま**
   - `bus/*.jsonl` を置いても scheduler、retry、heartbeat、idempotency がなければ運用基盤にはならない

2. **GitNexus の取り込みが弱い**
   - ただ `workspace.json` を置く発想に近く、`agent_graph_builder`、`context_resolver`、`MCP`、`reindex hooks` まで含む設計になっていない

3. **line-harness-oss の運用知見が入っていない**
   - event bus、cron、health log、notification rule、runbook、design constraints が未反映

4. **JSONL をそのまま本番 SSOT にしようとしている**
   - 小規模には有効だが、自律運用・再試行・分析・監視・複数 runner 連携には DB ベースが必要

5. **チーフ中心設計が残っている**
   - チーフがボトルネックである問題を解決するなら、チーフを「承認・方針・例外処理」に縮小し、通常タスクは control plane 経由にする必要がある

6. **builder / onboarding / docs 更新まで繋がっていない**
   - 現在の `CLAUDE.md.builder` と docx 群は旧アーキテクチャ前提のため、設計だけ直してもユーザーに再び古い構成を生成してしまう

7. **移行順序が危うい**
   - 現状資産を壊さず段階移行する計画になっていない

---

## 3. 調査結果に基づく統合方針

今回確認した各リポジトリの役割は明確です。

| 取り込み元 | 本当に使うもの | 使い方 |
|---|---|---|
| `my-virtual-team` | agent persona、guidelines、templates、builder、X投稿収集、利用者向け導線 | 業務知識・ブランド・生成資産として維持 |
| `agent-skill-bus` | Prompt Request schema、DAG 依存、file lock、skill-runs、skill-health、knowledge-diffs | **概念・スキーマ・CLI 互換**を採用。JSONL そのものは補助出力に落とす |
| `gitnexus-stable-ops` | `.gitnexus/workspace.json`、Agent Context Graph、context resolver、MCP、safe reindex | **Knowledge Plane の中核**としてそのまま取り込む |
| `line-harness-oss` | event bus、scheduled job、health log、notification rule、ops runbook、design constraints、DB-first 運用 | **Operations / Control Plane の設計パターン**として取り込む |

### 取り込むが、そのままは採用しないもの

- `agent-skill-bus` の JSONL only runtime
  - 理由: 自律運用の中核には弱い
- `line-harness-oss` の LINE CRM 固有ドメイン
  - 理由: 今回必要なのは CRM ではなく、運用設計と制御パターン
- 現在の `CLAUDE.md` の「チーフは自分で作業しない / 必ず委任」前提
  - 理由: 制御面をすべてチーフに背負わせる構成が既にボトルネック

---

## 4. v3 の設計原則

1. **Markdown は知識、DB は状態**
   - `agents/`, `guidelines/`, `templates/`, `docs/` は知識資産
   - task、lock、run、health、notification は durable store に置く

2. **Context は pull、Task は push**
   - コンテキストは GitNexus Agent Graph で都度最小取得
   - タスクは control plane へ enqueue して push 型で流す

3. **Chief は executor ではなく policy / approval / synthesis**
   - 通常 dispatch は control plane が行い、chief は高リスク判断と統合のみ担当

4. **ローカル first、常時稼働対応**
   - ローカル単体でも動く
   - そのまま D1 / Worker / webhook / cron に持ち上げられる

5. **JSONL は audit mirror**
   - `agent-skill-bus` 互換の JSONL/Markdown は export と人間可読用に残す
   - SSOT は SQLite/D1

6. **Builder まで含めて完成**
   - 新規導入時から v3 構成が生成される状態を完成条件にする

---

## 5. 目標アーキテクチャ

### 5.1 全体像

```text
User / Cron / Webhook / Knowledge Watcher / GitHub / LINE / Slack / Notion
                              |
                              v
                   Control Plane API / Runtime
                (SQLite local / D1 always-on compatible)
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
   Task Dispatcher      Event Bus           Health / Watchdog
   DAG / Lock / Retry   Notify / Sync       Timeout / Cleanup
          |
          v
   Runner Adapters
   - Claude Code
   - Codex
   - OpenClaw
   - GitHub Actions
   - Manual/Human
          |
          v
   Outputs / Task Events / Skill Runs / Handoffs
          ^
          |
   GitNexus Agent Context Graph
   - agent registry
   - skill refs
   - docs / data refs
   - workspace topology
```

### 5.2 4 Plane モデル

| Plane | 主責務 | 主な取り込み元 |
|---|---|---|
| Knowledge Plane | 必要最小コンテキストの探索、agent/skill/doc/data の関係管理 | `gitnexus-stable-ops` |
| Control Plane | task enqueue、DAG、lock、retry、approval、state transition | `agent-skill-bus` + `line-harness-oss` |
| Execution Plane | 各 runner が claim して実行し、結果を返す | `my-virtual-team` + 既存AIツール |
| Operations Plane | health、watcher、event、notification、cron、runbook | `line-harness-oss` |

### 5.3 SSOT の再定義

| 種類 | SSOT | 備考 |
|---|---|---|
| agent persona / brand / templates | 既存 Markdown (`agents/`, `guidelines/`, `templates/`) | 維持 |
| workspace topology | `.gitnexus/workspace.json` | 新設 |
| skill / agent metadata | frontmatter + registry file | 新設 |
| task state / lock / event / health | SQLite または D1 | 新設 |
| 人間向け監査ログ | JSONL / Markdown export | 補助 |
| builder / setup docs | Markdown source | docx は生成物へ移行 |

---

## 6. 目標ディレクトリ構成

```text
my-virtual-team/
├── CLAUDE.md
├── CLAUDE.md.builder
├── agents/                    # 既存維持 + frontmatter 追加
├── guidelines/                # 既存維持 + context tier 定義追加
├── templates/                 # 既存維持
├── data/                      # 既存維持（GitNexus data source 登録）
├── docs/
│   ├── v2-plan.md
│   ├── v3-plan.md
│   ├── architecture.md
│   ├── runbook.md
│   ├── schema.md
│   └── builder-migration.md
├── docs_src/                  # 新設。人間向けガイドの原本
├── .gitnexus/
│   ├── workspace.json
│   └── agent-graph.db
├── registry/                  # 新設。機械可読カタログ
│   ├── agents.json
│   ├── skills.json
│   ├── context-policy.json
│   └── integrations.json
├── runtime/                   # 新設。control plane の中心
│   ├── migrations/
│   ├── schema/
│   ├── services/
│   ├── jobs/
│   ├── adapters/
│   ├── cli/
│   └── exports/
├── skills/                    # 新設。runtime skill 群
│   ├── prompt-request-bus/
│   ├── self-improving-skills/
│   ├── knowledge-watcher/
│   ├── context-loader/
│   └── integrations/
├── outputs/                   # 新設。成果物・handoff
├── scripts/                   # 既存維持。runtime wrapper 化
└── .claude/
    ├── commands/              # 生成物化
    ├── rules/                 # context / dispatch / approval / reporting
    └── skills/
```

### 重要な構造変更

- `.claude/commands/*.md` は手書き運用から **registry/generated** に変える
- `logs/activity-log.json` のような配列 JSON 書き換えは廃止し、event log へ移す
- `scripts/slack-notify.sh` / `scripts/notion-sync.sh` は event bus adapter に置き換える
- `guidelines/top-posts-reference.md` のような大容量参照は context graph 上で tier 管理する

---

## 7. v3 のコアドメイン

### 7.1 Agent Registry

既存 `agents/*.md` を人間用定義のまま残しつつ、最低限の frontmatter を追加します。

必要属性:

- `agent_id`
- `department`
- `keywords`
- `skill_refs`
- `context_refs`
- `context_budget`
- `approval_policy`
- `execution_mode` (`direct` / `queue` / `review_only`)

### 7.2 Skill Registry

現在の `.claude/rules/` と `.claude/commands/` だけでは runtime skill として弱いため、  
`skills/` に再配置し、以下を持つようにします。

- owner agent
- trigger
- input schema
- output schema
- side effects
- affected path hints
- quality scoring rule
- watch sources

### 7.3 Task Model

`agent-skill-bus` の Prompt Request をベースにするが、DB では以下まで持つ。

- `tasks`
- `task_dependencies`
- `task_locks`
- `task_attempts`
- `task_events`
- `task_outputs`
- `task_approvals`
- `task_routing_decisions`

追加する必須概念:

- `idempotency_key`
- `runner_id`
- `heartbeat_at`
- `retry_count`
- `max_retries`
- `escalation_state`

### 7.4 Health / Quality Model

- `skill_runs`
- `skill_health_snapshots`
- `knowledge_diffs`
- `watch_sources`
- `health_logs`
- `notification_rules`
- `notifications`

これは `agent-skill-bus` の quality loop と `line-harness-oss` の health / notification 設計を合成したものです。

---

## 8. 主要フロー

### 8.1 Context Loading

1. ユーザー入力を受ける
2. `gitnexus_agent_context` で関連 agent / skill / doc / data を解決
3. 返却された file のみ読む
4. 不足時のみ depth を上げる

これにより、現状の「毎回全部読む」方式をやめる。

### 8.2 Task Dispatch

1. chief か webhook か watcher が task を作る
2. control plane に enqueue
3. DAG 展開・依存解決
4. affected path / lock を解決
5. runner が claim
6. heartbeat が止まれば timeout / retry
7. 完了時に output と event を記録

### 8.3 Self-Improvement

1. 実行結果を `skill_runs` に記録
2. trend を評価
3. 劣化や連続失敗を検知
4. watcher diff と突き合わせて root cause を推定
5. 自動修正 task か human review task を生成

### 8.4 Operations Event Bus

`line-harness-oss` の `fireEvent()` パターンを採用し、task lifecycle に応じて fan-out する。

対象イベント例:

- `task.created`
- `task.claimed`
- `task.completed`
- `task.failed`
- `task.timeout`
- `skill.degraded`
- `knowledge.diff_detected`
- `approval.requested`
- `notification.failed`

アクション例:

- Slack 通知
- Notion 記録
- LINE 通知
- GitHub issue / PR 生成
- health dashboard 更新

---

## 9. 実装フェーズ

### Phase 0: 設計固定と禁止事項の明文化

### 目的

先に設計の地雷を潰す。

### 実施内容

- `docs/architecture.md` 作成
- `docs/runbook.md` 作成
- `DESIGN_CONSTRAINTS.md` 新設
- chief, runner, DB, graph の責務境界を明文化

### 完了条件

- v3 の責務分離が文章で固定されている
- 今後の実装が「また CLAUDE.md に全部寄せる」方向へ戻らない

---

### Phase 1: Registry + Context Graph 化

### 目的

既存資産を壊さず、機械可読な知識基盤に変える。

### 実施内容

- `agents/*.md` に frontmatter 追加
- `guidelines/` を `always` / `on_demand` / `rare` tier に分類
- `.gitnexus/workspace.json` 新設
- `registry/agents.json` `registry/context-policy.json` 作成
- GitNexus Agent Graph をビルド可能にする
- `CLAUDE.md` に context loading protocol を導入

### 取り込むもの

- `gitnexus-stable-ops/lib/agent_graph_builder.py`
- `gitnexus-stable-ops/lib/context_resolver.py`
- `gitnexus-stable-ops/lib/mcp_server.py`
- `gitnexus-stable-ops` の reindex/hook 設計

### 完了条件

- 代表的な 10 タスクで `gitnexus_agent_context` が 5,000 tokens 以内で必要ファイルを返す
- `top-posts-reference.md` を毎回読む設計が消える

---

### Phase 2: Durable Control Plane 実装

### 目的

ファイル駆動の疑似運用をやめ、実行状態を durable にする。

### 実施内容

- SQLite schema 作成
- D1 互換 schema も同時定義
- task / dependency / lock / event / approval / output テーブル作成
- CLI or local API 実装
  - `enqueue`
  - `dispatch`
  - `claim`
  - `heartbeat`
  - `complete`
  - `fail`
  - `retry`
- JSONL export を追加し `agent-skill-bus` 互換を残す

### 取り込むもの

- `agent-skill-bus` の Prompt Request schema
- `line-harness-oss` の DB-first 運用思想

### 完了条件

- runner 再起動後も task 状態が失われない
- lock timeout / retry が動く
- 3 runner 並列で競合なく動作する

---

### Phase 3: Runner / Router / Chief 縮小

### 目的

chief ボトルネックを除去し、通常フローを control plane 化する。

### 実施内容

- `CLAUDE.md` を薄い orchestrator に再設計
- `.claude/commands/` を生成物に変更
- chief は以下のみ担当:
  - 初期意図の解釈
  - high-risk approval
  - 最終統合
- runner adapter を実装
  - Claude Code
  - Codex
  - OpenClaw
  - manual/human

### 完了条件

- 複数 agent タスクが chief 手動中継なしで進む
- chief は「全部自分で読む dispatcher」ではなく policy 層になっている

---

### Phase 4: Self-Improving + Knowledge Watcher

### 目的

壊れたあとに直すのではなく、劣化を検知して自律的に改善タスクを起こす。

### 実施内容

- `skill_runs` 記録
- `skill_health` 集計
- drift 検知
- watch source 定義
- diff 検知 job
- degrade -> repair task 自動生成

### 取り込むもの

- `agent-skill-bus/src/self-improve.js`
- `agent-skill-bus/src/knowledge-watcher.js`

### 完了条件

- API 仕様変更や skill failure から follow-up task が自動発火する
- 週次 health report が出る

---

### Phase 5: Event Bus + Integrations + Always-On 運用

### 目的

通知・同期・外部起動を shell script から event-driven に切り替える。

### 実施内容

- `runtime/services/event-bus.*` 実装
- Slack / Notion / LINE / GitHub adapter を event handler 化
- cron / webhook / scheduled job 実装
- health endpoint / dashboard / cleanup job 実装
- notification rule / retry / dead-letter 設計

### 取り込むもの

- `line-harness-oss/apps/worker/src/services/event-bus.ts`
- `line-harness-oss/packages/db/src/health.ts`
- `line-harness-oss/docs/wiki/22-Operations.md`

### 完了条件

- `scripts/slack-notify.sh` や `scripts/notion-sync.sh` を直接叩かなくても task event から通知が飛ぶ
- health / timeout / cleanup が定期実行される

---

### Phase 6: Builder / Docs / Productization

### 目的

新規セットアップ時点から v3 を生成できるようにする。

### 実施内容

- `CLAUDE.md.builder` を v3 対応に更新
- setup / usage guide を Markdown source 化
- docx は `docs_src/` から生成する形へ変更
- 新規チーム生成時に以下も自動作成:
  - `.gitnexus/workspace.json`
  - `registry/*`
  - `runtime/*`
  - `skills/*`
  - `outputs/`

### 完了条件

- 新規生成チームが最初から v3 アーキテクチャ
- 古い static-only 構成を再生成しない

---

### Phase 7: Hardening / Scale Test

### 目的

「動く」ではなく「壊れにくく運用できる」を完成させる。

### 実施内容

- failover / retry / backpressure test
- large task DAG test
- stale lock recovery test
- context graph stale detection test
- backup / restore 手順
- SLO / error budget 定義

### 完了条件

- 連続失敗、runner 停止、lock 取りっぱなし、watcher 暴走に耐える
- runbook だけで復旧できる

---

## 10. 優先順位

実装順は以下で固定する。

1. **Phase 1**
   - Context Graph がないと token 問題も routing も解けない
2. **Phase 2**
   - Durable state がないと scale しない
3. **Phase 3**
   - chief を細くして初めて並列実行が効く
4. **Phase 4**
   - 自己改善は基盤が固まってから
5. **Phase 5**
   - 外部連携は event 化して最後に統合
6. **Phase 6-7**
   - builder と hardening で仕上げる

---

## 11. 今回の設計で残すもの / 捨てるもの

### 残すもの

- `agents/` の人格・専門性
- `guidelines/` のブランド知識
- `templates/` の出力ひな形
- `scripts/collect-top-posts.js`
- builder 体験

### 捨てるもの

- 「チーフが全部読む」前提
- 手書き `.claude/commands/` 中心運用
- 状態を持たない static prompt system
- `logs/activity-log.json` のような配列 JSON 追記

### 補助に落とすもの

- JSONL queue
- Markdown history
- shell ベース通知

---

## 12. Definition of Done

この再設計が完了したと言える条件は以下です。

1. 新規チーム生成時に v3 構成が自動生成される
2. chief を介さず複数 agent が DAG ベースで並列稼働できる
3. context graph により不要ドキュメントの常時読込がなくなる
4. task / lock / run / health が durable store に残る
5. skill 劣化や外部変更から改善 task が自動起票される
6. Slack / Notion / LINE / GitHub 連携が event-driven で動く
7. runbook と health check だけで障害復旧できる

---

## 13. 最初の 2 週間でやるべき具体作業

### Week 1

- `.gitnexus/workspace.json` を定義
- `agents/*.md` に frontmatter 追加
- context tier を定義
- GitNexus Agent Graph をビルド
- `CLAUDE.md` を context-first に変更

### Week 2

- SQLite schema 作成
- task / dependency / lock / event テーブル作成
- CLI で enqueue / claim / complete 実装
- chief から direct dispatch ではなく queue dispatch へ切替開始

この 2 週間で「ただの prompt 集」から「制御面のある基盤」へ変わり始める。

---

## 14. 最終判断

`my-virtual-team` は、今のままだと「使い心地のよい static prompt kit」です。  
目指している「自律的に安定的に稼働し、スケールする仮想チーム」に必要なのは、  
`agent-skill-bus` のタスクモデル、`gitnexus-stable-ops` の context graph、`line-harness-oss` の運用制御を、
**1つの control plane に統合すること**です。

つまり v3 の本質は:

- prompt を増やすことではなく
- chief を賢くすることでもなく
- **状態、関係、イベント、品質を扱える基盤へ昇格させること**

です。
