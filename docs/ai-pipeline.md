# GitHub AI Pipeline

## 目的

`line-harness-oss` から一般化可能な GitHub AI pipeline を `my-virtual-team` に吸収する。

## 構成

- `claude-decompose.yml`
  issue に `claude` または `auto` label が付くと、Claude が atomic / decomposition を判定する
- `copilot-assign.yml`
  issue に `copilot` または `auto` label が付くと、Copilot coding agent を assign する
- `claude-review.yml`
  PR opened / synchronize / reopened で Claude review を行う
- `auto-merge.yml`
  review approved と check success 後に自動 merge を試みる
- `copilot-watchdog.yml`
  Copilot branch 上で `action_required` になった workflow を再実行する
- `gitnexus-impact.yml`
  PR changed files から impacted agents / skills / docs を自動コメントする
- `gitnexus-reindex.yml`
  merge 後に graph を再構築して artifact を残す
- `gitnexus-weekly.yml`
  週 1 回の full reindex を実行する
- `runtime-maintenance.yml`
  watcher / self-improve / health snapshot を定期実行する

## 必要な secrets

- `COPILOT_PAT`
  Copilot agent assign 用。`github.token` では足りない場合がある
- `ANTHROPIC_API_KEY`
  Claude review / decomposition 用
- または `CLAUDE_CODE_OAUTH_TOKEN_1..3`
  Claude Code OAuth token fallback

## 運用の基本形

1. issue を作る
2. `claude` か `auto` label を付ける
3. Claude が atomic 判定または sub-issue 分解を返す
4. atomic issue には `copilot` label が付き、Copilot が実装を開始する
5. PR が作られたら Claude review が走る
6. review / checks が揃えば auto-merge を試みる
7. 定期 maintenance と weekly reindex が裏側の health を保つ

## Secret 未設定時の挙動

- Claude secret がない場合:
  decomposition / review workflow は skip 理由を comment or review body に残す
- `COPILOT_PAT` がない場合:
  copilot assign workflow は skip comment を返す
- つまり secret 未設定でも generic pipeline 自体は壊れず、未設定理由が GitHub 上に出る

## いまの境界

- GitHub 上の generic AI pipeline はこの文書の workflow で扱う
- `runtime:task -- codex ...` は local runner
- Cloudflare deploy、LINE CRM 固有 rule、product-specific preview は吸収対象外
