# Phase 1 Findings

## 実装済み

- `agents/*.md` frontmatter を SSOT 化
- `registry/*.generated.json` と `AGENTS_CLAUDE.md` を自動生成
- `.gitnexus/workspace.json` を追加
- `.gitnexus/knowledge/` を GitNexus 向け curated mirror として生成
- `scripts/rebuild-agent-graph.sh` と `scripts/resolve-agent-context.sh` を追加
- agent-context 用の generated skills を `.claude/skills/generated/` に追加

## 今回見えた制約

- グローバル `gni` ラッパーはこの環境では `agent_graph_builder.py` を見つけられず壊れていた
- `knowledge_dir` を repo root にすると `agents/**/*.md` が KnowledgeDoc として入り、agent ID と衝突した
- GitNexus indexer はディレクトリ symlink を辿らないため、knowledge mirror は markdown 単位で張る必要があった
- 現状の graph には agent-skill edge がほぼなく、ranking は lexical match 依存が強い

## 現在の build 結果

- Agents: 8
- Skills: 7
- Knowledge Docs: 32
- Compute Nodes: 1
- Workspace Services: 3
- Edge Types: `USES_SKILL`, `DEPENDS_ON`, `RUNS_ON`

## representative query の結果

- `X投稿を作成して`
  - `x-post-context` が最上位
  - 朝比奈ユウが主担当として返る
  - `brand-guidelines`, `output-standards`, `philosophy`, `top-posts-summary` まで返る
- `API設計レビュー`
  - 桐島蓮と九条ハルが主担当として返る
  - `api-design-review`, `security-policy`, `output-standards` まで返る
- repo-local wrapper は既定で `--depth 1` を使い、共通 guideline 経由の 2-hop ノイズを抑えている

## 後続フェーズで反映済み

- `registry/skills.generated.json` を追加し、skill metadata を明示化した
- generated skill は build step に統合済み
- chief 側は `route / plan / start` で workflow を切る構成に更新済み
- repo-local CLI と graph rebuild flow を正式運用にした
- GitNexus builder / resolver は repo-local copy を標準とし、sibling repo 依存を外した
