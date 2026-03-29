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

## 自動 workflow

`.github/workflows/github-ops.yml` は以下で動く。

- `workflow_dispatch`
- `issues.opened`
- `issues.reopened`
- `issue_comment.created`
- `pull_request_target.opened`
- `pull_request_target.reopened`

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

この workflow が自動で行うのは route / plan / close までで、実際の repo 変更は local の `runtime:task -- codex ...` か GitHub Copilot assign で進める。

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
- 既定の native agent route では追加 secret は不要
- 実装担当は repo variable `VIRTUAL_TEAM_IMPLEMENTATION_AGENT` で差し替え可能
- PR mention は repo variable `VIRTUAL_TEAM_PR_AGENT_MENTION` で差し替え可能

## Native coding agent

この repo では既定で `copilot-swe-agent` を implementation agent として扱う。  
GitHub 側で Anthropic Claude や OpenAI Codex の third-party agent を有効化している場合は、repo variable を変えるだけで native route を切り替えられる。

実測では以下が確認できた。

- issue #5 を Copilot に assign
- Copilot が PR #6 を作成
- `docs/copilot-smoke.md` を追加
- PR #6 を merge
