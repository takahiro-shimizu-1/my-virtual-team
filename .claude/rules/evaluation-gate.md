# 評価ゲートプロトコル

品質保証のため、生成と評価を分離する。評価が必要な task は control plane 上で別 phase か approval として表現する。

## 評価ゲートが必要なもの

| アウトプット種別 | 対応 |
|---|---|
| 対外公開コンテンツ | draft + review/approval |
| 戦略・提案・見積 | draft + chief approval |
| 主要設計変更 | design + peer review + chief approval |
| 内部メモ・通常調査 | 原則 self-check |

## 運用ルール

1. 生成 phase と review phase を同一 task に混ぜない
2. approval pending の task は dispatch / claim しない
3. reviewer は生成者と別 agent を優先する
4. reviewer がいない場合は same agent の clean context 再起動を許可する
