# Execution Policy

## 目的

`my-virtual-team` は `Claude / Codex / Copilot / Gemini` を単に並べるのではなく、タスクの性質と必要能力に応じて選ぶ。

この方針は 3 つの source repo の意図を継承している。

## source repo から引き継いだ意図

### `line-harness-oss`

- 設計・レビュー・複雑実装は Claude Code
- Issue → Draft PR の単発実装は Copilot Coding Agent
- PR review は Claude Opus

根拠:

- `line-harness-oss/CLAUDE.md`
  `Claude Code (要件定義・Issue作成) -> Copilot Coding Agent -> CI -> Claude Opus 4.6 AI レビュー`
- 同文書の表
  `Claude Code (ローカル) | 設計・レビュー・複雑な実装`
  `Copilot Coding Agent | Issue -> PR 自動実装`

### `agent-skill-bus`

- セキュリティ・機密は Claude Code
- テスト追加・中規模機能は Copilot
- リサーチ・レポートは specialized research agent
- 大量リファクタは code-heavy agent

根拠:

- `agent-skill-bus/skills/coding-agent-router/SKILL.md`
  `security|secret|credential -> claude`
  `テスト.*追加|機能.*追加|feat|test.*add -> copilot`
  `リサーチ|調査|レポート|research|report -> manus`
  `全.*ファイル|大量|一括|refactor|migration -> cursor`

### `gitnexus-stable-ops`

- ここは主に context / workspace topology の repo で、どの LLM を選ぶかの強い routing policy は持たない
- ただし `workspace.json services[].model` を通じて「どの service がどの model を使っているか」は表現できる

根拠:

- `gitnexus-stable-ops/docs/agent-context-graph.md`
  `services[].model`

## 現在の policy

### `auto`

明示指定がなければ capability policy で選ぶ。

- `planning / review / strategy / requirements / architecture / security`
  `Claude` 寄り
- `research / report / competitive analysis`
  local は `Gemini` を優先
  fallback は `Claude`
- `large refactor / migration / rename / extract`
  `Codex` 寄り
- `single-task implementation / test addition / small docs update`
  GitHub native は `Copilot/default`
  local は `Codex`

### explicit override

明示ラベルや明示 provider は常に優先する。

- GitHub issue label `claude`
  `vt-implementation-claude`
- GitHub issue label `codex`
  `vt-implementation-codex`
- GitHub issue label `copilot`
  `vt-implementation-auto`
- local `--provider claude|codex|gemini`
  その provider を固定

## 実装場所

- route recommendation:
  `runtime/src/control/execution_policy.py`
  `runtime/src/control/router.py`
- durable task payload への埋め込み:
  `runtime/src/control/decomposer.py`
- local runner auto selection:
  `runtime/src/control/ai_runner.py`
- GitHub native custom agent selection:
  `scripts/github-agent-task.py`

## 注意

- `Gemini` は現在 local runner の正規 route
- GitHub native coding agent 側は `Copilot / Claude / Codex` を前提にしている
- したがって `Gemini` が必要な task を GitHub issue だけで完全自動実行する経路は、今は持たない
