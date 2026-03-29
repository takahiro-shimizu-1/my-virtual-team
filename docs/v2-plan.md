# my-virtual-team v2 改善計画

## 課題
1. 過剰なコンテキスト読み込み（マーケエージェント1回あたり~17Kトークン）
2. 選択的コンテキストなし（API開発にブランドガイドライン読み込み等）
3. エージェント間通信なし（チーフがボトルネック）
4. 並列実行の調整なし（ファイル競合リスク）
5. 非構造化ハンドオフ（フルテキスト丸投げ）
6. 品質フィードバックループなし

---

## Phase 1: トークン削減 + 構造化ハンドオフ（13ファイル）

### 1.1 context-index.json — NEW
- エージェントごとに always/on_demand/never のガイドライン分類
- トークン予算（context_budget）を定義

### 1.2 guidelines/top-posts-summary.md — NEW (~100トークン)
- 統計+Top5タイトルのみ

### 1.2b guidelines/top-posts-top20.md — NEW (~2,000トークン)
- 上位20件フルテキスト
- 既存 top-posts-reference.md (~14K) はLevel 3として残す

### 1.3 .claude/rules/agent-launch.md — MODIFY
- 「必須」のみ読む指示、段階的読み込みルール追加
- 依存: 1.2

### 1.4 .claude/rules/handoff-format.md — NEW
- outputs/handoff-{dagId}-{phase}.json 形式定義
- summary（500字以内）、requiredContext、nextPhase
- 依存: 1.6

### 1.5 .claude/rules/context-reset.md — MODIFY
- ハンドオフ形式への参照追加
- 依存: 1.4

### 1.6 outputs/.gitkeep — NEW

### 1.7 全8エージェント定義のコンテキストtier化 — MODIFY x8
- 参照guidelinesを必須/必要時/不要の3tierに分割
- 例: 桐島蓮 → brand-guidelines, philosophy, top-posts を「不要」に

**効果**: エージェントあたり 60-94% のトークン削減

---

## Phase 2: タスクキュー + 並列調整（12ファイル）

### 2.1 bus/ ディレクトリ初期化 — NEW x6
- prompt-request-queue.jsonl
- active-locks.jsonl
- dag-state.jsonl
- prompt-request-history.md
- skill-runs.jsonl
- skill-health.json

### 2.2 .claude/rules/task-dispatch.md — NEW
- 単発→直接起動、複数連携→Bus経由DAG分解
- affectedFilesによるファイルロック

### 2.3 DESIGN_CONSTRAINTS.md — NEW
- 全エージェント共通制約（出力先、ロック、コンテキスト、通信、セキュリティ）

### 2.4 workspace.json — NEW
- 全8エージェントのID、部門、キーワード、context_budget

### 2.5 CLAUDE.md — MODIFY
- ルーティングテーブル簡略化、workspace.json参照
- タスク管理セクション追加

### 2.6 全5部門ルーター — MODIFY x5
- DESIGN_CONSTRAINTS.md読み込み追加
- 選択的コンテキスト指示
- outputs/への出力指示

---

## Phase 3: 自己改善ループ（6ファイル）

### 3.1 .claude/rules/skill-logging.md — NEW
### 3.2 .claude/skills/health-check/SKILL.md — NEW
### 3.3 .claude/skills/knowledge-watch/SKILL.md — NEW
### 3.4 .claude/commands/health.md — NEW
### 3.5 .claude/commands/dispatch.md — NEW
### 3.6 .claude/skills/review/SKILL.md — MODIFY

---

## ファイル一覧（28ファイル）

| Phase | 新規 | 変更 |
|-------|------|------|
| 1 | context-index.json, top-posts-summary.md, top-posts-top20.md, handoff-format.md, outputs/.gitkeep (5) | agent-launch.md, context-reset.md, 8x agents (10) |
| 2 | 6x bus/*, task-dispatch.md, DESIGN_CONSTRAINTS.md, workspace.json (9) | CLAUDE.md, 5x commands (6) |
| 3 | skill-logging.md, health-check/SKILL.md, knowledge-watch/SKILL.md, health.md, dispatch.md (5) | review/SKILL.md (1) |
