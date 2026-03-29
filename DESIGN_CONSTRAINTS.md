# DESIGN_CONSTRAINTS.md — my-virtual-team

## SSOT

- MUST: agent metadata の正本は `agents/*.md` の frontmatter とする
- MUST: workspace topology の正本は `.gitnexus/workspace.json` とする
- MUST: task / lock / event / run / health の正本は durable store に置く
- NEVER: `registry/*.generated.json` を手編集しない
- NEVER: JSONL を本番の primary store にしない

## Context

- MUST: 起動時は frontmatter の `context_refs.always` だけを読む
- MUST: `context_refs.on_demand` はタスクに応じて追加で読む
- MUST: 大型タスクでは handoff の `requiredContext` のみ次フェーズへ渡す
- NEVER: `context_refs.never` を平常起動時に読む
- NEVER: `guidelines/top-posts-reference.md` を通常の投稿作成で常時読む

## Outputs

- MUST: 成果物は `outputs/` に出力する
- MUST: フェーズ間の受け渡しは handoff JSON で行う
- MUST: 次フェーズは `requiredContext` に列挙されたファイルだけを読む
- NEVER: サブエージェント出力の全文を次フェーズに丸投げしない

## Task Execution

- MUST: 単発タスクも含めて、すべての task を control plane に登録する
- MUST: lock 対象ファイルを task 作成時に宣言する
- MUST: state transition は監査可能な形で残す
- NEVER: file lock を無視して同一ファイルを並列更新しない

## Generated Files

- MUST: registry は `npm run registry:build` で再生成する
- MUST: `AGENTS_CLAUDE.md` は GitNexus 互換の生成物として扱う
- MUST: `.gitnexus/knowledge/` は GitNexus 用の curated mirror として生成する
- MUST: graph は fresh な状態でのみ利用する
- NEVER: stale graph のまま context resolver を信頼しない
- NEVER: `AGENTS_CLAUDE.md` を手編集しない

## Security

- MUST: `guidelines/security-policy.md` に従う
- NEVER: APIキー、トークン、パスワードを成果物やログに含めない
- NEVER: 未公開クライアント情報を外部向け成果物に含めない

## Migration

- MUST: Phase 0-1 は既存 `/strategy` `/development` `/marketing` `/research` `/admin` を壊さない
- MUST: 互換レイヤーを残したまま段階移行する
- NEVER: builder 更新前に旧構成を破壊して新規生成不能にしない
