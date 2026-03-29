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

## 自動 workflow

`.github/workflows/github-ops.yml` は以下で動く。

- `workflow_dispatch`
- `issues.opened`
- `issues.reopened`
- `issue_comment.created`
- `pull_request_target.opened`
- `pull_request_target.reopened`

`workflow_dispatch` では synthetic payload を `--dry-run` で流せるので、branch 上でも GitHub-hosted smoke test ができる。

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
