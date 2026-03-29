# 戦略・コンサル部

戦略系の依頼は `/strategy` で受け、owner を routing したうえで control plane に登録する。

## 担当

| キーワード・意図 | 担当 | ファイル |
|---|---|---|
| 事業戦略、成長計画、優先順位、方向性 | 鶴見 誠一 | `agents/01-strategy/tsurumin-seiichi.md` |
| 要件定義、ヒアリング、仕様整理 | 水野 あかり | `agents/01-strategy/mizuno-akari.md` |
| 提案書、AI活用提案、見積、ROI | 堀江 遼 | `agents/01-strategy/horie-ryo.md` |

## 実行手順

1. `npm run runtime:task -- route --command strategy --prompt "$ARGUMENTS"` で owner を確認する
2. 単発なら `npm run runtime:task -- start --command strategy --prompt "$ARGUMENTS" --runner chief`
3. 提案→要件のような複数工程なら `npm run runtime:task -- plan --command strategy --prompt "$ARGUMENTS" --dispatch`
4. approval pending があれば chief が `approve` してから次段へ進める

## 評価ゲート

- 提案書・戦略計画: 生成後に chief approval
- 大きな方向転換: 鶴見 誠一を最終 reviewer 候補にする

$ARGUMENTS
