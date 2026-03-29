# GitHub AI Pipeline

## 目的

`line-harness-oss` から一般化可能な GitHub AI pipeline を `my-virtual-team` に吸収しつつ、既定は GitHub subscription-native agents で動かす。

## 構成

- `claude-decompose.yml`
  issue に `claude` または `auto` label が付くと、repo-local planner が atomic / decomposition を判定し、subscription-based implementation flow へ渡す
- `copilot-assign.yml`
  issue に `copilot` または `auto` label が付くと、既定で subscription-native coding agent kickoff を実行する
- `claude-review.yml`
  PR opened / synchronize / reopened で既定の native agent mention を投稿する
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

## 既定の実行方式

- 既定:
  `github.token` + GitHub Copilot / third-party agent subscription
- 実装担当 agent:
  repo variable `VIRTUAL_TEAM_IMPLEMENTATION_AGENT`
  未設定時は `copilot-swe-agent`
- PR mention agent:
  repo variable `VIRTUAL_TEAM_PR_AGENT_MENTION`
  未設定時は `@copilot`

`@claude` や `@codex` など GitHub 側で有効化された third-party agent に切り替えたい場合は repo variable だけ差し替えればよい。

GitHub-hosted kickoff は `VIRTUAL_TEAM_GH_USER_TOKEN` を優先し、未設定時だけ `github.token` にフォールバックする。現在の repo では前者を既定にしている。

## 任意の API fallback

必要なら vendor CLI / API ベースの workflow に戻せるが、それは既定ではない。  
この repo の既定ルートは subscription-native agents である。

## 運用の基本形

1. issue を作る
2. `claude` か `auto` label を付ける
3. local planner が atomic 判定または sub-issue 分解を返す
4. atomic issue には `copilot` label が付き、GitHub Actions が subscription-native coding agent task を自動起動する
5. PR が作られたら native review handoff comment が走る
6. review / checks が揃えば auto-merge を試みる
7. 定期 maintenance と weekly reindex が裏側の health を保つ

## Secret 未設定時の挙動

native route 自体は vendor API secret 不要。  
ただし GitHub Actions から user-authenticated に起動するため、既定では `VIRTUAL_TEAM_GH_USER_TOKEN` を使う。

## いまの境界

- GitHub 上の generic AI pipeline はこの文書の workflow で扱う
- `runtime:task -- codex ...` は local runner
- Cloudflare deploy、LINE CRM 固有 rule、product-specific preview は吸収対象外
