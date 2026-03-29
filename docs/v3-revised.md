# my-virtual-team v3 改訂実装計画

**作成日**: 2026-03-29
**ベース**: v3-plan.md（設計思想・アーキテクチャ）を踏襲し、実装の具体性・即効性・移行安全性を補強

---

## 0. v3-plan.md からの変更点

| 項目 | v3 原案 | 改訂版 |
|------|---------|--------|
| Phase数 | 8（0〜7） | 6（0〜5）— Phase 6-7を統合 |
| 即効改善 | Phase 1以降 | Phase 0に含める（初日から効果） |
| ファイルリスト | 方針レベル | Phase別に全ファイル明記 |
| 参照元ファイルパス | 一部不正確 | 全て実ファイルパスで記載 |
| 既存システム並行運用 | 未記載 | 各Phaseに明記 |
| JSONL→SQLite移行 | 即時SQLite | Phase 2はJSONL(agent-skill-bus互換)で開始、Phase 5でSQLite化 |
| Context tier | 概念のみ | 全8エージェント×7ガイドラインの具体分類表 |

---

## 1. アーキテクチャ（v3原案を踏襲）

### 4 Plane モデル

```
                    ユーザー / cron / webhook / watcher
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Control Plane     │  ← agent-skill-bus CLI + データ
                    │   task / DAG / lock │
                    └────────┬────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        Task Dispatch   Event Bus     Health/Watchdog
              │         (通知/同期)    (劣化検知)
              ▼
        Runner (Claude Code / Codex / OpenClaw)
              │
              ▼
        outputs/ + skill-runs + handoff
              ▲
              │
    ┌─────────────────────┐
    │  Knowledge Plane    │  ← gitnexus-stable-ops
    │  Agent Context Graph│
    │  context resolver   │
    └─────────────────────┘
```

### 設計原則（v3原案と同一）

1. **Markdownは知識、永続ストアは状態** — agents/, guidelines/, templates/ は知識資産。task/lock/run/healthは永続化
2. **Contextはpull、Taskはpush** — GitNexus Agent Graphで最小取得、タスクはqueue経由push
3. **Chiefはpolicy/approval/synthesis** — 通常dispatchはcontrol plane、chiefは高リスク判断と統合のみ
4. **ローカルfirst、常時稼働対応** — ローカル単体で動き、D1/Worker/cronに持ち上げ可能
5. **JSONLはaudit mirror** — agent-skill-bus互換JSONL/Markdownは人間可読用に残す

---

## 2. 参照元の実資産マッピング

### agent-skill-bus（そのまま使えるもの）

| 資産 | パス | 用途 |
|------|------|------|
| CLI（16コマンド） | `agent-skill-bus/src/cli.js` | enqueue/dispatch/start/complete/fail/stats/health/flagged/drift/dashboard/diffs/locks/dag/record-run/init/paths |
| JSOLNキュー | `agent-skill-bus/src/queue.js` | PromptRequestQueue — DAG依存解決、ファイルロック、TTL |
| スキル監視 | `agent-skill-bus/src/self-improve.js` | SkillMonitor — score追跡、trend検知、drift検出 |
| 知識監視 | `agent-skill-bus/src/knowledge-watcher.js` | KnowledgeWatcher — 外部変更検知、diff記録 |
| PR スキーマ | `agent-skill-bus/src/queue.js` | id, source, priority, agent, task, context, affectedSkills, affectedFiles, deadline, status, dependsOn, dagId |
| スキルディレクトリ（14個） | `agent-skill-bus/skills/` | prompt-request-bus, self-improving-skills, knowledge-watcher, x-scheduler等 |

### gitnexus-stable-ops（そのまま使えるもの）

| 資産 | パス | 用途 |
|------|------|------|
| Agent Graph Builder | `gitnexus-stable-ops/lib/agent_graph_builder.py` (52K) | workspace構造解析→SQLite agent-graph.db構築 |
| Context Resolver | `gitnexus-stable-ops/lib/context_resolver.py` (28K) | FTS5クエリ解決、progressive disclosure（Level 1〜3） |
| MCP Server | `gitnexus-stable-ops/lib/mcp_server.py` (14K) | Claude/エージェントからのagent graph照会 |
| Context Generator | `gitnexus-stable-ops/lib/context_gen.py` (24K) | CLAUDE.md/AGENTS.md自動生成 |
| Workspace Builder | `gitnexus-stable-ops/lib/workspace_builder.py` (28K) | workspace.json解析、マルチリポ対応 |
| CLI Wrapper | `gitnexus-stable-ops/bin/gni` (10K) | agent-index, agent-status, agent-list, agent-context コマンド |
| Agent Indexer | `gitnexus-stable-ops/bin/gitnexus-agent-index.sh` | agent graph ビルド/リビルド |
| Smart Reindexer | `gitnexus-stable-ops/bin/gitnexus-agent-reindex.sh` | タイムスタンプ追跡付きインクリメンタル更新 |
| workspace.jsonスキーマ | `gitnexus-stable-ops/docs/workspace-schema.md` | version, workspace_root, nodes, services, knowledge_refs |

### line-harness-oss（パターンとして取り込むもの）

| パターン | 参照元 | 適用方法 |
|----------|--------|----------|
| DESIGN_CONSTRAINTS形式 | `line-harness-oss/DESIGN_CONSTRAINTS.md` | カテゴリ別制約 + MUST/NEVER + コード例 |
| Event Bus | `line-harness-oss/apps/worker/src/services/event-bus.ts` | fireEvent() + Promise.allSettled()による並列handler |
| DB Migration | `line-harness-oss/packages/db/migrations/001_*.sql〜014_*.sql` | 番号付きSQL順次適用 |
| Health監視 | `line-harness-oss/packages/db/src/health.ts` | risk level (normal/warning/danger) + 定期チェック |
| 運用Wiki | `line-harness-oss/docs/wiki/22-Operations.md` | 日次監視項目、cronジョブ、障害対応手順 |
| Multi-agent Pipeline | `line-harness-oss/CLAUDE.md` | Claude Code→Copilot→CI→AI Review→Auto-merge |

---

## 3. コンテキストtier設計（全8エージェント×7ガイドライン）

### tier定義

| tier | 意味 | 読み込みタイミング |
|------|------|-------------------|
| **always** | エージェントの基本動作に必須 | 毎回起動時に読む |
| **on_demand** | タスク内容によって必要 | タスクが該当領域に触れる場合のみ |
| **never** | そのエージェントには不要 | 読まない |

### 分類表

| エージェント | company-overview | brand-guidelines | output-standards | security-policy | escalation-rules | philosophy | top-posts-reference |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 鶴見誠一（戦略） | always | on_demand | always | never | never | on_demand | never |
| 水野あかり（要件） | always | on_demand | always | never | never | never | never |
| 堀江遼（提案） | always | on_demand | always | never | never | on_demand | never |
| 桐島蓮（Web開発） | always | never | always | on_demand | never | never | never |
| 九条ハル（AI開発） | always | never | always | on_demand | never | never | never |
| 朝比奈ユウ（マーケ） | always | always | always | never | never | on_demand | on_demand※ |
| 藤堂理人（リサーチ） | always | never | always | on_demand | never | never | never |
| 小宮さくら（管理） | always | never | always | on_demand | on_demand | never | never |

※ 朝比奈ユウの top-posts-reference は3段階:
- 通常: `top-posts-summary.md` (~100トークン) を読む
- 投稿作成時: `top-posts-top20.md` (~2,000トークン) を読む
- 深い分析時のみ: `top-posts-reference.md` (~14,000トークン) を読む

### トークン削減効果

| エージェント | 現状(トークン) | always tier | 削減率 |
|-------------|------:|------:|------:|
| 鶴見誠一 | ~3,100 | ~1,100 | **65%** |
| 水野あかり | ~1,900 | ~1,100 | **42%** |
| 堀江遼 | ~3,100 | ~1,100 | **65%** |
| 桐島蓮 | ~2,300 | ~1,100 | **52%** |
| 九条ハル | ~2,300 | ~1,100 | **52%** |
| 朝比奈ユウ | ~17,100 | ~1,900 | **89%** |
| 藤堂理人 | ~2,300 | ~1,100 | **52%** |
| 小宮さくら | ~2,800 | ~1,100 | **61%** |

---

## 4. 実装フェーズ

---

### Phase 0: 即効改善 + 設計基盤

**目的**: 初日からトークン削減効果を出しつつ、以降のPhaseの設計基盤を固める

**並行運用**: 既存の `/strategy` `/development` 等は全てそのまま動作。追加・変更のみ。

#### 新規作成ファイル（10ファイル）

| ファイル | 内容 | 参照元 |
|---------|------|--------|
| `guidelines/top-posts-summary.md` | 統計+Top5タイトル (~100トークン) | top-posts-reference.md から抽出 |
| `guidelines/top-posts-top20.md` | 上位20件フルテキスト (~2,000トークン) | top-posts-reference.md から抽出 |
| `outputs/.gitkeep` | 成果物・ハンドオフ出力先 | — |
| `.claude/rules/handoff-format.md` | 構造化ハンドオフ形式定義 | agent-skill-bus PR schema参考 |
| `DESIGN_CONSTRAINTS.md` | 全エージェント共通制約 | line-harness-oss/DESIGN_CONSTRAINTS.md パターン |
| `docs/architecture.md` | 4 Plane アーキテクチャ文書 | v3-plan.md §5 |
| `docs/runbook.md` | 運用手順書 | line-harness-oss/docs/wiki/22-Operations.md パターン |
| `docs/schema.md` | データスキーマ一覧 | agent-skill-bus PR schema + gitnexus workspace schema |
| `registry/context-policy.json` | エージェント×ガイドライン tier定義 | §3 の分類表 |
| `registry/agents.json` | 全8エージェントの機械可読メタデータ | 各agents/*.md から抽出 |

#### 変更ファイル（12ファイル）

| ファイル | 変更内容 |
|---------|---------|
| `.claude/rules/agent-launch.md` | tier読み込みルール追加: always tierのみ読む指示、on_demand条件、registry/context-policy.json参照 |
| `.claude/rules/context-reset.md` | ハンドオフ形式(handoff-format.md)への参照追加。次フェーズはrequiredContextのみ読む指示 |
| `agents/01-strategy/tsurumin-seiichi.md` | 参照guidelinesを3tier形式に変更 |
| `agents/01-strategy/mizuno-akari.md` | 同上 |
| `agents/01-strategy/horie-ryo.md` | 同上 |
| `agents/02-development/kirishima-ren.md` | 同上 |
| `agents/02-development/kujo-haru.md` | 同上 |
| `agents/03-marketing/asahina-yu.md` | 同上 + top-posts 3段階参照に変更 |
| `agents/04-research/todo-rito.md` | 同上 |
| `agents/05-admin/komiya-sakura.md` | 同上 |
| `CLAUDE.md` | DESIGN_CONSTRAINTS.md参照追加、outputs/使用指示追加 |
| `.claude/rules/reporting-format.md` | outputs/ へのhandoff出力ルール追加 |

#### handoff-format.md の形式定義

```json
{
  "dagId": "task-20260329-abc",
  "phase": 1,
  "agent": "mizuno-akari",
  "summary": "要件定義完了。機能要件5件、非機能要件3件を整理（500字以内）",
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

#### registry/agents.json の構造

```json
{
  "version": "1.0",
  "agents": [
    {
      "agent_id": "tsurumin-seiichi",
      "name": "鶴見 誠一",
      "department": "01-strategy",
      "department_name": "戦略・コンサル部",
      "file": "agents/01-strategy/tsurumin-seiichi.md",
      "keywords": ["事業戦略", "成長計画", "AGIロードマップ", "方向性"],
      "skill_refs": [],
      "context_budget": 3000,
      "approval_policy": "major_direction_change",
      "execution_mode": "direct",
      "evaluation_gate": {
        "required": true,
        "evaluator": "tsurumin-seiichi",
        "criteria": "ビジネス整合性"
      },
      "collaborators": ["horie-ryo", "todo-rito"]
    }
  ]
}
```

#### registry/context-policy.json の構造

```json
{
  "version": "1.0",
  "tiers": {
    "always": "毎回起動時に読む",
    "on_demand": "タスクが該当領域に触れる場合のみ",
    "never": "読まない"
  },
  "guidelines": {
    "company-overview": { "path": "guidelines/company-overview.md", "tokens": 600 },
    "brand-guidelines": { "path": "guidelines/brand-guidelines.md", "tokens": 800 },
    "output-standards": { "path": "guidelines/output-standards.md", "tokens": 500 },
    "security-policy": { "path": "guidelines/security-policy.md", "tokens": 400 },
    "escalation-rules": { "path": "guidelines/escalation-rules.md", "tokens": 500 },
    "philosophy": { "path": "guidelines/philosophy.md", "tokens": 1200 },
    "top-posts-summary": { "path": "guidelines/top-posts-summary.md", "tokens": 100 },
    "top-posts-top20": { "path": "guidelines/top-posts-top20.md", "tokens": 2000 },
    "top-posts-reference": { "path": "guidelines/top-posts-reference.md", "tokens": 14000 }
  },
  "agents": {
    "tsurumin-seiichi": {
      "always": ["company-overview", "output-standards"],
      "on_demand": ["brand-guidelines", "philosophy"],
      "never": ["security-policy", "escalation-rules", "top-posts-summary", "top-posts-top20", "top-posts-reference"]
    },
    "mizuno-akari": {
      "always": ["company-overview", "output-standards"],
      "on_demand": ["brand-guidelines"],
      "never": ["security-policy", "escalation-rules", "philosophy", "top-posts-summary", "top-posts-top20", "top-posts-reference"]
    },
    "horie-ryo": {
      "always": ["company-overview", "output-standards"],
      "on_demand": ["brand-guidelines", "philosophy"],
      "never": ["security-policy", "escalation-rules", "top-posts-summary", "top-posts-top20", "top-posts-reference"]
    },
    "kirishima-ren": {
      "always": ["company-overview", "output-standards"],
      "on_demand": ["security-policy"],
      "never": ["brand-guidelines", "escalation-rules", "philosophy", "top-posts-summary", "top-posts-top20", "top-posts-reference"]
    },
    "kujo-haru": {
      "always": ["company-overview", "output-standards"],
      "on_demand": ["security-policy"],
      "never": ["brand-guidelines", "escalation-rules", "philosophy", "top-posts-summary", "top-posts-top20", "top-posts-reference"]
    },
    "asahina-yu": {
      "always": ["company-overview", "output-standards", "brand-guidelines"],
      "on_demand": ["philosophy", "top-posts-summary", "top-posts-top20"],
      "never": ["security-policy", "escalation-rules"],
      "progressive": {
        "top-posts": {
          "default": "top-posts-summary",
          "content_creation": "top-posts-top20",
          "deep_analysis": "top-posts-reference"
        }
      }
    },
    "todo-rito": {
      "always": ["company-overview", "output-standards"],
      "on_demand": ["security-policy"],
      "never": ["brand-guidelines", "escalation-rules", "philosophy", "top-posts-summary", "top-posts-top20", "top-posts-reference"]
    },
    "komiya-sakura": {
      "always": ["company-overview", "output-standards"],
      "on_demand": ["escalation-rules", "security-policy"],
      "never": ["brand-guidelines", "philosophy", "top-posts-summary", "top-posts-top20", "top-posts-reference"]
    }
  }
}
```

#### DESIGN_CONSTRAINTS.md の構造（line-harness-oss準拠）

```markdown
# DESIGN_CONSTRAINTS.md — my-virtual-team

## 出力先制約
- MUST: 成果物は outputs/ に出力する
- MUST: ハンドオフは outputs/handoff-{dagId}-{phase}.json 形式
- NEVER: 他エージェントの管轄ファイルを直接編集しない

## コンテキスト制約
- MUST: registry/context-policy.json の always tier のみ起動時に読む
- MUST: on_demand tier はタスク内容に応じて判断
- NEVER: never tier を読み込まない

## ファイルロック制約
- MUST: 同一ファイルへの並列書き込みを避ける（bus/active-locks.jsonl参照）
- MUST: ロック取得は affectedFiles を事前申告

## 通信制約
- MUST: フェーズ間受け渡しは handoff JSON 経由（フルテキスト丸投げ禁止）
- MUST: 次フェーズは requiredContext に指定されたファイルのみ読む

## セキュリティ制約
- NEVER: APIキー、トークン、パスワードを成果物に含めない
- NEVER: 未公開クライアントデータを外部向け成果物に含めない
- MUST: guidelines/security-policy.md に準拠

## 品質制約
- MUST: 対外公開コンテンツは評価ゲートを通す
- MUST: タスク完了時に skill-runs を記録する（Phase 4以降）
```

#### 完了条件

- [ ] 朝比奈ユウ起動時の読み込みトークンが ~1,900（always tier のみ）
- [ ] 全エージェントがtier化された参照guidelinesで起動可能
- [ ] outputs/ にhandoff JSONが出力できる
- [ ] DESIGN_CONSTRAINTS.md が全エージェントから参照される

---

### Phase 1: Agent Context Graph 構築

**目的**: GitNexus Agent Context Graph でコンテキスト解決を自動化する

**並行運用**: Phase 0 の tier ルールはそのまま有効。Agent Graph は追加の最適化レイヤー。

#### 新規作成ファイル（3ファイル）

| ファイル | 内容 | 参照元 |
|---------|------|--------|
| `.gitnexus/workspace.json` | ワークスペース定義（agents, skills, knowledge_refs） | `gitnexus-stable-ops/docs/workspace-schema.md` |
| `AGENTS.md` | 全エージェント一覧（context_gen.pyが自動生成） | `gitnexus-stable-ops/lib/context_gen.py` |
| `registry/skills.json` | スキルカタログ（review, 各部門ルーター） | — |

#### 変更ファイル（9ファイル）

| ファイル | 変更内容 |
|---------|---------|
| `agents/01-strategy/tsurumin-seiichi.md` | frontmatter追加（agent_id, department, keywords, skill_refs, context_refs, context_budget, approval_policy, execution_mode） |
| `agents/01-strategy/mizuno-akari.md` | 同上 |
| `agents/01-strategy/horie-ryo.md` | 同上 |
| `agents/02-development/kirishima-ren.md` | 同上 |
| `agents/02-development/kujo-haru.md` | 同上 |
| `agents/03-marketing/asahina-yu.md` | 同上 |
| `agents/04-research/todo-rito.md` | 同上 |
| `agents/05-admin/komiya-sakura.md` | 同上 |
| `CLAUDE.md` | context loading protocol追加（`gni agent-context`による最小取得フロー） |

#### frontmatter 形式

```yaml
---
agent_id: kirishima-ren
department: 02-development
keywords: [Web開発, フロント, バックエンド, API, DB, インフラ, GCP]
skill_refs: [code-review, technical-design]
context_refs:
  always: [guidelines/company-overview.md, guidelines/output-standards.md]
  on_demand: [guidelines/security-policy.md]
context_budget: 3000
approval_policy: major_architecture_change
execution_mode: direct
---
```

#### workspace.json

```json
{
  "version": "1.1",
  "workspace_root": "MY_VIRTUAL_TEAM",
  "description": "shimizu個人事業主の仮想AIチーム",
  "nodes": [
    {
      "id": "local",
      "name": "shimizu-wsl",
      "role": "primary",
      "os": "linux",
      "access": { "type": "local" },
      "workspace_root": ".",
      "services": ["claude-code", "gitnexus"]
    }
  ],
  "services": [
    {
      "id": "claude-code",
      "name": "Claude Code Runner",
      "type": "agent",
      "node": "local"
    },
    {
      "id": "gitnexus",
      "name": "GitNexus MCP",
      "type": "tool",
      "node": "local"
    }
  ],
  "knowledge_refs": {
    "skills_dir": ".claude/skills",
    "memory_dir": "docs",
    "knowledge_dir": "guidelines"
  }
}
```

#### 実行手順

```bash
# 1. workspace.json配置後、agent graphをビルド
cd my-virtual-team
gni agent-index .

# 2. ビルド結果確認
gni agent-status
gni agent-list

# 3. コンテキスト解決テスト（代表的なタスク10件）
gni agent-context "X投稿を作成して"
gni agent-context "API設計をレビューして"
gni agent-context "競合分析をして"
# → 各クエリが 5,000 tokens 以内で必要ファイルを返すことを確認
```

#### 完了条件

- [ ] `gni agent-index` が正常完了し `.gitnexus/agent-graph.db` が生成される
- [ ] `gni agent-context` で代表10タスクが 5,000 tokens 以内で解決される
- [ ] AGENTS.md が自動生成される
- [ ] 全8エージェントのfrontmatterがパース可能

---

### Phase 2: Control Plane（agent-skill-bus統合）

**目的**: agent-skill-busのタスクキュー・DAG・ロック機構をmy-virtual-teamに統合する

**並行運用**: 既存コマンドはそのまま動作。bus/ は追加レイヤー。`/dispatch` は新規コマンド。

#### 新規作成ファイル（9ファイル）

| ファイル | 内容 | 参照元 |
|---------|------|--------|
| `bus/prompt-request-queue.jsonl` | タスクキュー（空ファイルで初期化） | agent-skill-bus/skills/prompt-request-bus/ |
| `bus/active-locks.jsonl` | ファイルロック状態 | 同上 |
| `bus/dag-state.jsonl` | DAG実行状態 | 同上 |
| `bus/prompt-request-history.md` | 完了タスク履歴 | 同上 |
| `bus/skill-runs.jsonl` | スキル実行ログ | agent-skill-bus/skills/self-improving-skills/ |
| `bus/skill-health.json` | スキルヘルス集計 | 同上 |
| `.claude/rules/task-dispatch.md` | タスクディスパッチルール | — |
| `.claude/commands/dispatch.md` | `/dispatch` コマンド定義 | — |
| `registry/integrations.json` | 外部連携定義（Slack, Notion等） | — |

#### 変更ファイル（6ファイル）

| ファイル | 変更内容 |
|---------|---------|
| `CLAUDE.md` | タスク管理セクション追加。bus/ 参照、dispatch フロー、ルーティングテーブルを workspace.json + registry/agents.json 参照に簡略化 |
| `.claude/commands/strategy.md` | DESIGN_CONSTRAINTS.md読み込み追加、outputs/出力指示、選択的コンテキスト指示 |
| `.claude/commands/development.md` | 同上 |
| `.claude/commands/marketing.md` | 同上 |
| `.claude/commands/research.md` | 同上 |
| `.claude/commands/admin.md` | 同上 |

#### task-dispatch.md の内容

```markdown
# タスクディスパッチルール

## 判断基準

| 条件 | ディスパッチ方法 |
|------|-----------------|
| 単発タスク（1エージェント） | 直接起動（従来通り） |
| 複数エージェント連携 | Bus経由DAG分解 |
| 定期タスク | cron → Bus enqueue |
| 外部トリガー | webhook → Bus enqueue |

## Bus経由フロー

1. `skill-bus enqueue` でタスク登録
2. `skill-bus dispatch` で次タスク取得
3. DAG依存が解決済みのタスクのみ実行
4. `skill-bus start <id>` でロック取得
5. エージェント実行
6. `skill-bus complete <id>` または `skill-bus fail <id>`

## ファイルロック

- enqueue時に `affectedFiles` を申告
- start時に active-locks.jsonl にロック記録
- 競合するファイルを持つタスクは dispatch されない
- TTL: 7200秒（2時間）。超過時は自動fail
```

#### 完了条件

- [ ] `npx agent-skill-bus enqueue` → `dispatch` → `start` → `complete` の一連フローが動作
- [ ] 2エージェント並列実行で outputs/ への書き込みが競合しない
- [ ] DAG依存（A→Bの順序）が正しく解決される
- [ ] `/dispatch` コマンドでDAG分解→実行ができる

---

### Phase 3: Chief縮小 + Runner統合

**目的**: Chiefを「全部自分で読むdispatcher」から「policy/approval/synthesis」に縮小する

**並行運用**: 既存コマンドは引き続き動作。CLAUDE.mdの役割記述が変わるが、破壊的変更なし。

#### 新規作成ファイル（1ファイル）

| ファイル | 内容 |
|---------|------|
| `runtime/adapters/README.md` | Runner adapter 設計メモ（Claude Code / Codex / OpenClaw） |

#### 変更ファイル（2ファイル）

| ファイル | 変更内容 |
|---------|---------|
| `CLAUDE.md` | Chief役割を再定義: (1)初期意図の解釈 (2)high-risk approval (3)最終統合。通常タスクはbus経由dispatch。ルーティングテーブルを registry/agents.json の keywords 参照に切替 |
| `.claude/rules/agent-launch.md` | bus経由起動テンプレートを追加。直接起動と bus起動の使い分け指示 |

#### CLAUDE.md 改訂構成

```markdown
# shimizu — 仮想チーム司令塔

## Chiefの役割（v3）
1. **意図解釈**: ユーザーの指示を明確化し、registry/agents.jsonでルーティング
2. **承認**: escalation-rules.md に該当する判断の最終承認
3. **統合**: 複数エージェントの結果を統合して報告

## タスクディスパッチ
- 単発タスク → 従来通り直接起動
- 複数連携タスク → /dispatch でDAG分解
- 詳細: .claude/rules/task-dispatch.md

## エージェント検索
- registry/agents.json の keywords でマッチング
- .gitnexus agent-context で関連エージェント特定

## 制約
- DESIGN_CONSTRAINTS.md を遵守
- outputs/ に成果物を出力
- bus/ でタスク状態を管理
```

#### 完了条件

- [ ] 複数エージェントタスクがchief手動中継なしで進む（bus経由）
- [ ] chiefは registry/agents.json のkeywordsでルーティングし、エージェント定義全文を毎回読まない
- [ ] 直接起動（単発）と bus起動（複数連携）が共存

---

### Phase 4: Self-Improving + Knowledge Watcher

**目的**: スキル劣化を検知し、自律的に改善タスクを起こす

**並行運用**: Phase 0-3の全機能はそのまま。スキルログと監視は追加レイヤー。

#### 新規作成ファイル（6ファイル）

| ファイル | 内容 | 参照元 |
|---------|------|--------|
| `.claude/rules/skill-logging.md` | 全タスク完了時のskill-runs記録ルール | agent-skill-bus/src/self-improve.js |
| `.claude/skills/health-check/SKILL.md` | ヘルスチェックスキル（OBSERVE→ANALYZE→DIAGNOSE→PROPOSE→EVALUATE→REPORT） | agent-skill-bus/skills/self-improving-skills/SKILL.md |
| `.claude/skills/knowledge-watch/SKILL.md` | guidelines/変更検知→影響エージェント特定→通知 | agent-skill-bus/skills/knowledge-watcher/SKILL.md |
| `.claude/commands/health.md` | `/health` コマンド | — |
| `bus/knowledge-state.json` | 知識ソース状態 | agent-skill-bus/skills/knowledge-watcher/ |
| `bus/knowledge-diffs.jsonl` | 知識変更差分ログ | 同上 |

#### 変更ファイル（1ファイル）

| ファイル | 変更内容 |
|---------|---------|
| `.claude/skills/review/SKILL.md` | 実行ログ記録 + スキルヘルス概要表示を追加 |

#### skill-logging.md の内容

```markdown
# スキル実行ログルール

## 記録タイミング
全タスク完了時に以下を記録する:

## 記録方法
skill-bus record-run \
  --agent "{エージェントID}" \
  --skill "{スキル名}" \
  --task "{タスク概要}" \
  --result "{success|fail|partial}" \
  --score "{0.0-1.0}" \
  --notes "{補足}"

## スコア基準
| 結果 | score |
|------|-------|
| 完全に要求を満たした | 0.9-1.0 |
| 概ね満たしたが軽微な修正あり | 0.7-0.8 |
| 部分的に完了 | 0.4-0.6 |
| 失敗・やり直し | 0.0-0.3 |

## ヘルスチェック
skill-bus health --days 7
skill-bus flagged
skill-bus drift
```

#### 完了条件

- [ ] タスク完了時に bus/skill-runs.jsonl に記録が追加される
- [ ] `skill-bus health` でスキルヘルスサマリーが表示される
- [ ] `skill-bus drift` でスコア劣化が検知される
- [ ] `/health` コマンドで全体状況が確認できる
- [ ] guidelines/ の変更が knowledge-diffs.jsonl に記録される

---

### Phase 5: Event Bus + 永続化 + 仕上げ

**目的**: 通知をevent-driven化し、状態永続化をSQLiteに昇格させ、builder含め完成させる

**注**: Phase 0-4が安定稼働してから着手する。ここまでのJSONL運用で問題が出なければSQLite化は延期可能。

#### 新規作成ファイル（7ファイル）

| ファイル | 内容 | 参照元 |
|---------|------|--------|
| `runtime/services/event-bus.js` | fireEvent() + Promise.allSettled() パターン | line-harness-oss/apps/worker/src/services/event-bus.ts |
| `runtime/adapters/slack.js` | Slack通知adapter | scripts/slack-notify.sh を置き換え |
| `runtime/adapters/notion.js` | Notion同期adapter | scripts/notion-sync.sh を置き換え |
| `runtime/migrations/001_initial.sql` | SQLite schema（tasks, locks, events, runs, health） | line-harness-oss/packages/db/migrations/ パターン |
| `runtime/schema/tables.md` | テーブル定義ドキュメント | — |
| `docs/builder-migration.md` | CLAUDE.md.builder v3対応ガイド | — |
| `.claude/commands/health.md` (更新) | `/health` にSQLiteクエリ版を追加 | — |

#### 変更ファイル（3ファイル）

| ファイル | 変更内容 |
|---------|---------|
| `CLAUDE.md` | 通知をevent bus経由に変更。scripts/直接呼び出しを非推奨化 |
| `CLAUDE.md.builder` | v3アーキテクチャ対応。新規チーム生成時に registry/, bus/, outputs/, .gitnexus/ を含む |
| `scripts/log-activity.sh` | event bus adapter呼び出しに内部変更（既存インターフェースは維持） |

#### Event Bus イベント定義

```javascript
// 対象イベント
const EVENTS = {
  'task.created':    [notifySlack],
  'task.completed':  [notifySlack, syncNotion, recordActivity],
  'task.failed':     [notifySlack, createFollowUp],
  'skill.degraded':  [notifySlack, createRepairTask],
  'knowledge.diff':  [notifyAffectedAgents],
  'approval.needed': [notifySlack],
};

// handler は Promise.allSettled で並列実行
async function fireEvent(eventType, payload) {
  const handlers = EVENTS[eventType] || [];
  await Promise.allSettled(handlers.map(h => h(payload)));
}
```

#### SQLite Schema（Phase 0-4のJSONLからの移行）

```sql
-- 001_initial.sql
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,           -- human|system|auto
  priority TEXT NOT NULL,         -- critical|high|medium|low
  agent TEXT NOT NULL,
  task TEXT NOT NULL,
  context TEXT,
  affected_files TEXT,            -- JSON array
  affected_skills TEXT,           -- JSON array
  deadline TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  result TEXT,
  dag_id TEXT,
  idempotency_key TEXT UNIQUE,
  runner_id TEXT,
  heartbeat_at TEXT,
  retry_count INTEGER DEFAULT 0,
  max_retries INTEGER DEFAULT 3,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE task_dependencies (
  task_id TEXT NOT NULL REFERENCES tasks(id),
  depends_on TEXT NOT NULL REFERENCES tasks(id),
  PRIMARY KEY (task_id, depends_on)
);

CREATE TABLE task_locks (
  file_path TEXT NOT NULL,
  task_id TEXT NOT NULL REFERENCES tasks(id),
  agent TEXT NOT NULL,
  locked_at TEXT NOT NULL,
  ttl INTEGER DEFAULT 7200,
  PRIMARY KEY (file_path)
);

CREATE TABLE task_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT REFERENCES tasks(id),
  event_type TEXT NOT NULL,
  payload TEXT,                   -- JSON
  created_at TEXT NOT NULL
);

CREATE TABLE skill_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent TEXT NOT NULL,
  skill TEXT NOT NULL,
  task TEXT NOT NULL,
  result TEXT NOT NULL,           -- success|fail|partial
  score REAL NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE skill_health (
  skill TEXT PRIMARY KEY,
  runs INTEGER DEFAULT 0,
  avg_score REAL DEFAULT 0,
  recent_avg REAL DEFAULT 0,
  trend TEXT DEFAULT 'stable',
  consecutive_fails INTEGER DEFAULT 0,
  flagged INTEGER DEFAULT 0,
  updated_at TEXT NOT NULL
);

CREATE TABLE knowledge_diffs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  diff_type TEXT NOT NULL,
  detail TEXT NOT NULL,
  affected_skills TEXT,           -- JSON array
  severity TEXT NOT NULL,
  processed INTEGER DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type TEXT NOT NULL,
  channel TEXT NOT NULL,          -- slack|notion|line|github
  payload TEXT,                   -- JSON
  status TEXT DEFAULT 'pending',  -- pending|sent|failed
  retry_count INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  sent_at TEXT
);
```

#### 完了条件

- [ ] task eventからSlack通知がevent bus経由で飛ぶ
- [ ] SQLiteにタスク状態が永続化される（runner再起動後も状態維持）
- [ ] CLAUDE.md.builder で新規チームがv3構成で生成される
- [ ] health/timeout/cleanupが定期実行可能

---

## 5. 全ファイル一覧（36ファイル）

| Phase | 新規作成 | 変更 | 計 |
|-------|---------|------|--:|
| 0 | context-policy.json, agents.json, top-posts-summary.md, top-posts-top20.md, handoff-format.md, DESIGN_CONSTRAINTS.md, architecture.md, runbook.md, schema.md, outputs/.gitkeep | agent-launch.md, context-reset.md, reporting-format.md, CLAUDE.md, 8× agents/*.md | 22 |
| 1 | workspace.json, AGENTS.md, skills.json | 8× agents/*.md (frontmatter), CLAUDE.md | 12 |
| 2 | 6× bus/*, task-dispatch.md, dispatch.md, integrations.json | CLAUDE.md, 5× commands/*.md | 15 |
| 3 | runtime/adapters/README.md | CLAUDE.md, agent-launch.md | 3 |
| 4 | skill-logging.md, health-check/SKILL.md, knowledge-watch/SKILL.md, health.md, knowledge-state.json, knowledge-diffs.jsonl | review/SKILL.md | 7 |
| 5 | event-bus.js, slack.js, notion.js, 001_initial.sql, tables.md, builder-migration.md | CLAUDE.md, CLAUDE.md.builder, log-activity.sh, health.md | 10 |

※ Phase間で同一ファイルへの変更は累積（例: CLAUDE.mdはPhase 0,1,2,3,5で段階的に変更）

---

## 6. 移行安全性

### 原則

**各Phase完了後も、既存の全スラッシュコマンド（/strategy等）はそのまま動作する。**

### Phase別の後方互換性

| Phase | 既存機能への影響 |
|-------|----------------|
| 0 | 影響なし。tier化はエージェント定義内の記述変更のみ。起動テンプレートは従来互換 |
| 1 | 影響なし。frontmatterは既存Markdown本文の前に追加。Agent Graphは追加レイヤー |
| 2 | 影響なし。bus/は新規ディレクトリ。既存コマンドは直接起動のまま動作。/dispatchは純粋追加 |
| 3 | CLAUDE.md改訂。ただし既存コマンドのルーティングは維持。chiefの記述が変わるのみ |
| 4 | 影響なし。skill-runs記録とヘルスチェックは純粋追加 |
| 5 | scripts/*.sh の内部変更のみ。外部インターフェースは維持 |

### ロールバック

各Phaseは独立してロールバック可能:
- Phase 0: agents/*.md のtier記述を元に戻す、追加ファイル削除
- Phase 1: frontmatter削除、.gitnexus/ 削除
- Phase 2: bus/ 削除、CLAUDE.md のタスク管理セクション削除
- Phase 3: CLAUDE.md を Phase 2 版に戻す
- Phase 4: bus/skill-runs.jsonl 等削除、ルール削除
- Phase 5: runtime/ 削除、scripts/ を直接呼び出しに戻す

---

## 7. 検証計画

| Phase | テスト | 成功基準 |
|-------|--------|---------|
| 0 | 朝比奈ユウを起動してトークン数確認 | always tier のみ ~1,900 tokens |
| 0 | handoff JSON を outputs/ に出力 | 形式が handoff-format.md に準拠 |
| 1 | `gni agent-context "X投稿を作成"` | 朝比奈ユウ + brand-guidelines + top-posts-summary が返る |
| 1 | `gni agent-context "API設計レビュー"` | 桐島蓮 + security-policy が返る |
| 2 | 水野あかり(要件)→桐島蓮(設計) のDAG実行 | dependsOn が正しく解決、handoff経由で引き継ぎ |
| 2 | 九条ハル + 桐島蓮 の並列実行 | active-locks で outputs/ ファイル競合なし |
| 3 | 複数エージェント連携タスクをbus経由で実行 | chief が中継せずDAGで進行 |
| 4 | 5タスク実行後に `/health` | skill-health.json にトレンド表示 |
| 4 | guidelines/brand-guidelines.md を変更 | knowledge-diffs.jsonl に記録、影響エージェント特定 |
| 5 | タスク完了イベント発火 | Slack通知がevent bus経由で届く |

---

## 8. Definition of Done

1. ✅ 全エージェントがcontext tierに基づく最小トークンで起動する
2. ✅ Agent Context Graphでタスクに応じたコンテキスト解決ができる
3. ✅ chiefを介さず複数agentがDAGベースで並列稼働できる
4. ✅ task/lock/run/healthが永続ストアに残る
5. ✅ skill劣化や外部変更から改善taskが自動起票される
6. ✅ Slack/Notion連携がevent-drivenで動く
7. ✅ runbookとhealth checkだけで障害復旧できる
8. ✅ 新規チーム生成時にv3構成が自動生成される
