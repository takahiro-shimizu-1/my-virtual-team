# 開発部

開発系の依頼は `/development` で受け、routing 結果に応じて fast path か DAG へ登録する。

## 担当

| キーワード・意図 | 担当 | ファイル |
|---|---|---|
| Web開発、バックエンド、API、DB、インフラ | 桐島 蓮 | `agents/02-development/kirishima-ren.md` |
| AI開発、LLM、RAG、プロンプト、エージェント設計 | 九条 ハル | `agents/02-development/kujo-haru.md` |

## 実行手順

1. `npm run runtime:task -- route --command development --prompt "$ARGUMENTS"`
2. 単発実装なら `npm run runtime:task -- start --command development --prompt "$ARGUMENTS" --runner chief`
3. AI設計→実装、API設計→レビューのような複数工程は `plan --dispatch`
4. 実装完了後は `outputs/` に成果物、必要なら handoff JSON を残す

## 評価ゲート

- API設計レビュー: 桐島 蓮 ↔ 九条 ハル の相互レビュー
- 主要アーキテクチャ変更: chief approval

$ARGUMENTS
