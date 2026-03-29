# my-virtual-team

## このリポジトリの目的

`my-virtual-team` は、AI 仮想チームを運用するためのマルチエージェント基盤です。Knowledge Plane / Control Plane / Execution Plane / Operations Plane を分離し、タスクのルーティング、承認、実行、イベント連携を一貫して扱います。

主な用途は次のとおりです。

- agent / skill / document の関係を管理し、必要な文脈だけを解決する
- task を DB で管理し、claim / approval / retry / timeout を制御する
- GitHub Issue / PR を運用チャネルとして受け付ける
- activity log / Slack / Notion / GitHub へイベントを fan-out する

## Quickstart

前提:

- Node.js 18 以上
- Python 3
- GitHub 連携を使う場合は `gh auth login` または `GH_TOKEN` / `GITHUB_TOKEN`

初回セットアップ:

```bash
npm run bootstrap
```

これで registry build、graph build、runtime migrate、v4 validation をまとめて実行します。fresh clone 直後はまずこれを 1 回流してください。

動作確認:

```bash
npm run ci:verify
```

日常運用では `runtime:task` と `graph:context` が必要な準備を自動で行います。
local で docs / code を実際に生成する場合は `npm run runtime:task -- codex ...` を使います。

## 主要コマンド

```bash
npm run bootstrap
npm run ci:verify
npm run runtime:task -- route --command development --prompt "API設計レビューをお願いします"
npm run runtime:task -- start --command development --prompt "API設計レビューをお願いします" --runner chief
npm run runtime:task -- codex --prompt "README.md を整備して" --command admin --target-path README.md
npm run runtime:task -- plan --command strategy --prompt "提案をまとめて、その後要件も整理して" --dispatch
npm run runtime:health
npm run runtime:events
npm run runtime:watch
```

補助コマンド:

- `npm run graph:context`: task に必要な context を解決する
- `npm run registry:build`: registry を再生成する
- `npm run graph:build`: Agent Context Graph を再構築する
- `npm run runtime:migrate`: `.runtime/state.db` を最新 schema に合わせる
- `npm run validate:v4`: active docs と runtime 構成の整合を検証する

`agents/`、`guidelines/`、`templates/`、`.claude/` 配下などを更新した場合は、`npm run registry:build` と `npm run graph:build` を再実行してください。

## GitHub Issue / PR 運用

この repo では GitHub Issue / PR を運用チャネルとして扱います。workflow の中心は route / plan / close と Copilot assign で、Issue / PR が開かれると route が解決され、owner / skill / approval_required / required_context が自動コメントされます。

代表的な手動操作:

```bash
./scripts/github-issue.sh github-issue-create --title "調査依頼" --body "API設計レビューをしたい"
./scripts/github-issue.sh github-issue-update --issue-number 12 --label development --body "追加要件あり"
./scripts/github-issue.sh github-issue-close --issue-number 12 --comment "完了"
./scripts/github-pr-comment.sh --pr-number 3 --body "route summary を更新しました"
```

コメントコマンド:

- `/vt route`
- `/vt plan`
- `/vt route 任意の依頼文`
- `/vt plan 任意の依頼文`
- `/vt issue close`

`/vt issue close` は `OWNER / MEMBER / COLLABORATOR` のみ実行できます。payload 確認だけしたい場合は `--dry-run` を付けてください。

## Copilot 連携

GitHub Issue を `copilot-swe-agent` に assign すると、Copilot coding agent に作業を渡せます。

```bash
./scripts/github-issue.sh github-issue-assign --issue-number 5 --assignee copilot-swe-agent
```

`github-issue-create --assignee copilot-swe-agent` でも assign できます。GitHub-hosted の smoke test は次で実行できます。

```bash
gh workflow run github-ops.yml --ref <branch> -f scenario=issues -f prompt='API設計レビューをお願いします'
```

## 関連ドキュメント

- [Runbook](docs/runbook.md): bootstrap、task 実行、health、watch、障害時チェック
- [GitHub Operations](docs/github-ops.md): Issue / PR 運用、slash command、認証、Copilot assign
- [Architecture](docs/architecture.md): 4 Plane 構成、SSOT、core flow
- [Copilot Smoke Tests](docs/copilot-smoke.md): GitHub event bridge と smoke test の確認項目
