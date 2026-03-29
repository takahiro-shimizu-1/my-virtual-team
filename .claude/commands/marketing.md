# マーケティング部

マーケティング系の依頼は `/marketing` で受け、公開リスクを見ながら tracked fast path で進める。

## 担当

| キーワード・意図 | 担当 | ファイル |
|---|---|---|
| SNS投稿、X運用、スレッド、コンテンツ企画、発信 | 朝比奈 ユウ | `agents/03-marketing/asahina-yu.md` |

## 実行手順

1. `npm run runtime:task -- route --command marketing --prompt "$ARGUMENTS"`
2. 通常の投稿案は `start`
3. ドラフト→セルフレビューが必要な依頼は `plan --dispatch`
4. approval pending の公開物は chief が承認してから確定する

## 評価ゲート

- 対外公開コンテンツは approval 対象
- `x-post-context` が match したら `required_context` を優先する

$ARGUMENTS
