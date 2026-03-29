# Handoff Format

フェーズをまたぐ task では、成果物そのものに加えて handoff JSON を `outputs/` に出力する。

## 形式

```json
{
  "dagId": "task-20260329-abc",
  "phase": 1,
  "agent": "mizuno-akari",
  "summary": "500字以内の要約",
  "outputs": ["outputs/requirements-spec-20260329.md"],
  "requiredContext": [
    "outputs/requirements-spec-20260329.md",
    "guidelines/company-overview.md"
  ],
  "nextPhase": {
    "agent": "kirishima-ren",
    "task": "要件に基づく技術設計"
  },
  "completedAt": "2026-03-29T10:30:00+09:00"
}
```

## ルール

- `summary` は 500 字以内
- `outputs` は成果物の実ファイルパス
- `requiredContext` には次フェーズが読むべきファイルだけを列挙する
- `nextPhase` は未定なら省略可
