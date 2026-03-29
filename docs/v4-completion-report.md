# v4 Completion Report

## 結論

`my-virtual-team` の v4 フェーズと GitHub operations extension は完了した。現在の repo は `frontmatter + GitNexus + SQLite runtime + event-driven ops + GitHub issue/PR bridge + local Codex runner + builder contract` を満たしている。

## 完了したもの

- Phase 0: frontmatter SSOT、registry build、top-posts tier 化
- Phase 1: GitNexus workspace、repo-local graph rebuild、representative resolver tuning
- Phase 2: SQLite durable store、task lifecycle、approval / retry / timeout、JSONL mirror
- Phase 3: chief 縮小、route / plan / start / approve、department command 更新
- Phase 4: event bus、activity log / Slack / Notion / GitHub adapter、health、local watcher
- Phase 5: builder migration、repo-local GitNexus、GitHub Actions validation、GitHub issue / PR bridge workflow、local Codex runner、`validate:v4`、runbook / schema / architecture / todo 更新

## 現在の運用コマンド

```bash
npm run ci:verify
npm run bootstrap
npm run registry:build
npm run graph:build
npm run runtime:migrate
npm run runtime:test
npm run runtime:watch
npm run runtime:events
npm run runtime:health
npm run runtime:github-bridge -- handle --event-name issues --event-path event.json --dry-run
npm run runtime:task -- codex --prompt "README.md を整備して" --command admin --target-path README.md
npm run validate:v4
```

通常利用では `runtime:task` が registry build と migrate を自動実行し、`graph:context` は graph freshness を自動で整える。
registry 生成物は内容が変わらない限り再書き込みしないため、普段の task 実行で repo が毎回 dirty になることもない。
GitHub 上では `.github/workflows/validate.yml` が同じ検証を走らせる。
Issue / PR 運用では `.github/workflows/github-ops.yml` が route / plan の自動応答を返す。
実際の repo 変更は local の `runtime:task -- codex ...` か GitHub Copilot assign で進める。

## representative behavior

- `runtime:task route --command development --prompt "API設計レビュー"` で開発系 owner と review skill が解決される
- `runtime:task start --command development --prompt "Web APIの実装方針を整理して"` で fast path が claim される
- `runtime:task codex --prompt "README.md を整備して" --command admin --target-path README.md` で Codex が claim / execute / complete する
- `runtime:task start --command marketing --prompt "X投稿案を作って"` は approval pending で止まる
- `runtime:task plan --command strategy --prompt "提案をまとめて、その後要件も整理して" --dispatch` で multi-phase workflow が作られる
- GitHub Issue / PR が開かれると owner / skill / approval_required / required_context を自動コメントする
- `/vt route` と `/vt plan` が issue / PR comment から dry-run できる

## 非目標として残したもの

- LINE adapter
- OpenClaw 本番 adapter
- 外部 RSS / competitor watcher
- JSONL primary store

## 完了判定

この repo では、未完のフェーズは残っていない。今後は v5 ではなく、個別の運用拡張か productization の仕事になる。
