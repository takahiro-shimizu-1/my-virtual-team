# GitHub Operations

## 目的

GitHub Issue / PR を `my-virtual-team` の運用チャネルとして扱えるようにする。

## 手動操作

Issue 作成:

```bash
./scripts/github-issue.sh github-issue-create \
  --title "API設計レビューをしたい" \
  --body "現状APIの認可設計を見直したい"
```

Issue 更新:

```bash
./scripts/github-issue.sh github-issue-update \
  --issue-number 12 \
  --body "追記: 認証フローも含めてレビューしたい" \
  --label development
```

Issue close:

```bash
./scripts/github-issue.sh github-issue-close \
  --issue-number 12 \
  --comment "完了したので close します"
```

PR comment:

```bash
./scripts/github-pr-comment.sh \
  --pr-number 3 \
  --body "review plan を task に登録しました"
```

`--dry-run` を付けると `gh api` を実行せず、送信予定 payload だけ確認できる。

Native coding agent へ assign:

```bash
./scripts/github-issue.sh github-issue-assign \
  --issue-number 5 \
  --assignee copilot-swe-agent
```

`github-issue-create --assignee copilot-swe-agent` も内部で GraphQL assign にフォールバックする。

user-authenticated subscription route:

```bash
npm run github:agent-task -- issue --issue-number 7 --follow
```

これは `gh agent-task create` を使う。現在の repo では GitHub Actions も同じ native route を `VIRTUAL_TEAM_GH_USER_TOKEN` 経由で既定利用するので、通常は人手で打つ必要はない。上のコマンドは smoke / diagnosis 用。

必要なら custom agent を明示できる。

```bash
npm run github:agent-task -- prompt --text "README.md を整備して" --custom-agent vt-implementation-claude --dry-run
```

## 自動 workflow

`.github/workflows/github-ops.yml` は以下で動く。

- `workflow_dispatch`
- `issues.opened`
- `issues.reopened`
- `issue_comment.created`

`workflow_dispatch` では synthetic payload を `--dry-run` で流せるので、branch 上でも GitHub-hosted smoke test ができる。

別系統の AI implementation pipeline は `docs/ai-pipeline.md` を参照。

## 自動応答

Issue / PR が開かれると:

- route を解決する
- owner / skill / approval_required / required_context をコメントする

Comment で以下を使える。

- `/vt route`
- `/vt plan`
- `/vt route 任意の依頼文`
- `/vt plan 任意の依頼文`
- `/vt issue close`

`/vt issue close` は `OWNER / MEMBER / COLLABORATOR` のみ実行できる。

この workflow が自動で行うのは route / plan / close までで、issue 実装開始は別 workflow の subscription-native coding agent kickoff が担当する。

## linked task fan-out

task payload に以下を持たせると、`runtime:events` が GitHub にも fan-out する。

```json
{
  "github": {
    "repo": "owner/repo",
    "issue_number": 12,
    "close_on_complete": true
  }
}
```

または `pr_number` を持たせれば PR conversation comment へ送る。

## 認証

- local: `gh auth login` 済み、または `GH_TOKEN` / `GITHUB_TOKEN`
- GitHub Actions: `secrets.GITHUB_TOKEN`
- autonomous native kickoff: `secrets.VIRTUAL_TEAM_GH_USER_TOKEN`
  GitHub Actions runner 上で `gh auth login --with-token` に使う
- 実装担当は repo variable `VIRTUAL_TEAM_IMPLEMENTATION_AGENT` で差し替え可能
- PR mention は repo variable `VIRTUAL_TEAM_PR_AGENT_MENTION` で差し替え可能

## Native coding agent

この repo の GitHub-native route は custom agent profile を使って provider を固定できる。

- `vt-implementation-auto`: repo default / auto model selection
- `vt-implementation-claude`: Claude Sonnet 4.5
- `vt-implementation-codex`: GPT-5.2-Codex

issue に `claude` または `codex` label が付いた場合、workflow は対応する custom agent を `gh agent-task create --custom-agent ...` で起動する。`auto` / `copilot` は `vt-implementation-auto` を使う。

`Gemini` はこの repo では local runner を正規 route とする。GitHub native coding agent 側には載せていない。

実運用上の正規 path は 1 つである。

- GitHub-hosted default:
  issue label -> workflow -> `gh auth login --with-token` -> `gh agent-task create --custom-agent vt-implementation-*`

この経路は GitHub subscription に紐づくユーザー文脈で起動するため、vendor API key なしで native agent を動かせる。現在の repo では maintainer の `gh auth` を repo secret 化してあり、利用者が別途手動起動する前提はない。

実測では以下が確認できた。

- issue #5 を Copilot に assign
- Copilot が PR #6 を作成
- `docs/copilot-smoke.md` を追加
- PR #6 を merge
