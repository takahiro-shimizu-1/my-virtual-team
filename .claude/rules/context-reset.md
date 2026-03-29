# コンテキストリセット

大型タスクでは phase ごとにコンテキストを切り替え、次フェーズへ渡す情報を `requiredContext` に限定する。

## 基本ルール

- 中間成果物は `outputs/` に保存する
- phase をまたぐときは handoff JSON も `outputs/` に保存する
- 次フェーズは handoff の `requiredContext` に列挙されたファイルだけを読む
- agent frontmatter の `always` は毎 phase で読み直してよい
- `on_demand` は次フェーズで必要なときだけ追加する

## 適用判断

| 条件 | コンテキストリセット |
| --- | --- |
| 単発タスク（SNS投稿、簡単な調査等） | 不要 |
| 中規模タスク（記事作成、競合分析、要件定義から実装計画まで） | 推奨（2-3 phase） |
| 大型タスク（戦略策定、事業計画、設計から実装まで） | 必須（3-4 phase） |

## handoff の要件

- 形式は `.claude/rules/handoff-format.md` を使う
- `summary` は短く保ち、詳細は成果物に逃がす
- `requiredContext` は次フェーズに本当に必要なものだけに絞る
