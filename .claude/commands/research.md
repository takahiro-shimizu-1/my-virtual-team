# リサーチ部

調査依頼は `/research` で受け、必要なら strategy / development へ handoff できる形で記録する。

## 担当

| キーワード・意図 | 担当 | ファイル |
|---|---|---|
| 技術調査、論文、ツール比較、市場調査、競合分析 | 藤堂 理人 | `agents/04-research/todo-rito.md` |

## 実行手順

1. `npm run runtime:task -- route --command research --prompt "$ARGUMENTS"`
2. 単発調査は `start`
3. 後段で提案や実装に渡す場合は `plan --dispatch` で phase を分ける
4. レポートは `outputs/` に残し、事実ソースと未確定点を明示する

## 評価ゲート

- 一般的な内部調査は自己チェック中心
- 有料調査や機密情報を含むものは chief approval

$ARGUMENTS
