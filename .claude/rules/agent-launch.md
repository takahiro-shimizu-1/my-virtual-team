# サブエージェント起動ルール

chief は task を直接投げず、先に control plane に登録する。

## 基本手順

1. `runtime:task route` で owner / collaborator / required_context を決める
2. `runtime:task start` または `runtime:task plan --dispatch` で task を登録する
3. runner が claim したら、対象 agent の定義ファイルと required_context だけを読む
4. 完了時は `complete` / `fail` で state を閉じる

## 起動テンプレート

```text
runner:
  agent_file: {agents/...}
  required_context:
    - frontmatter.context_refs.always
    - route.required_context
  never_read:
    - frontmatter.context_refs.never
  output:
    - reusable artifact -> outputs/
    - phase handoff -> outputs/handoff-*.json
```

## ポイント

- task registration をバイパスしない
- frontmatter が metadata の SSOT
- generated registry は lookup 補助
- full context を毎回読まず、required_context を優先する
