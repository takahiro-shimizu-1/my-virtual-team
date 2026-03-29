# 管理部

管理系の依頼は `/admin` で受け、金額・契約・法務の確認を explicit に残す。

## 担当

| キーワード・意図 | 担当 | ファイル |
|---|---|---|
| 請求書、経費、契約、freee、期限管理 | 小宮 さくら | `agents/05-admin/komiya-sakura.md` |

## 実行手順

1. `npm run runtime:task -- route --command admin --prompt "$ARGUMENTS"`
2. 単発の整理作業は `start`
3. 契約レビューや複数工程の事務フローは `plan --dispatch`
4. 金額や法務判断を伴う task は chief approval 後に進める

## 評価ゲート

- 請求・契約・法務判断は approval 必須
- 対外送付前の成果物は最終確認を残す

$ARGUMENTS
