# サブエージェント起動ルール

chief が sub-agent を起動する際は、frontmatter を SSOT として最小コンテキストで起動する。

## 起動テンプレート

```text
{runner}:
  description: "{エージェント名} - {タスク概要}"
  prompt: |
    あなたは shimizu の{エージェント名}です。

    ## あなたの定義
    - `{エージェントファイルパス}` を読み、frontmatter と本文を把握してください
    - 初期読み込みは frontmatter の `context_refs.always` のみです
    - `context_refs.on_demand` は、タスク遂行に必要なものだけ追加で読んでください
    - `context_refs.never` は平常起動では読まないでください

    ## タスク
    指示: 「{指示内容}」

    ## 出力ルール
    - あなたの定義ファイルの「アウトプット形式」に従って出力すること
    - 再利用価値のある成果物は `outputs/` に保存すること
    - 次フェーズへ渡す場合は handoff JSON を `outputs/` に保存すること
    - 判断に迷う場合は「確認が必要」と明記すること
```

## ポイント

- 正本は `agents/*.md` の frontmatter であり、generated registry は参照補助にとどめる
- guidelines を起動時に全部読むのではなく、必要な tier だけ読む
- phase をまたぐ場合は `.claude/rules/handoff-format.md` に従う
- agent 名とファイルパスは各部門ルーターまたは registry 生成物から解決してよいが、矛盾時は agent ファイルを優先する
