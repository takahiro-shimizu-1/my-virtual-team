# GitHub AI Pipeline

## 目的

`line-harness-oss` から一般化可能な GitHub AI pipeline を `my-virtual-team` に吸収しつつ、既定は GitHub subscription-native agents で動かす。

## 構成

- `issue-native-plan.yml`
  issue に `auto` `copilot` `claude` `codex` のいずれかが付くと、repo-local planner が atomic / decomposition を判定し、subscription-based implementation flow へ渡す
- `native-agent-kickoff.yml`
  issue に `auto` `copilot` `claude` `codex` のいずれかが付くと、`VIRTUAL_TEAM_GH_USER_TOKEN` で認証して subscription-native coding agent kickoff を実行する
- `agent-pr-verify.yml`
  open な native agent PR を対象に explicit dispatch され、PR head を default-branch 文脈で checkout して `ci:verify` を実行し、そのまま review handoff と impact report まで完結させる
- `native-agent-review.yml`
  互換のため残している legacy workflow
- `auto-merge.yml`
  review approved と check success 後に自動 merge を試みる
- `native-agent-watchdog.yml`
  managed agent run と review 系 workflow の監視、および open な native agent PR への `agent-pr-verify` dispatch 用
- `gitnexus-impact.yml`
  互換のため残している legacy workflow
- `gitnexus-reindex.yml`
  merge 後に graph を再構築して artifact を残す
- `gitnexus-weekly.yml`
  週 1 回の full reindex を実行する
- `runtime-maintenance.yml`
  watcher / self-improve / health snapshot を定期実行する

## 既定の実行方式

- 既定:
  `VIRTUAL_TEAM_GH_USER_TOKEN` + GitHub native coding agent subscription
- 実装担当 agent:
  repo variable `VIRTUAL_TEAM_IMPLEMENTATION_AGENT`
  未設定時は bundled custom agent profile (`vt-implementation-auto`, `vt-implementation-claude`, `vt-implementation-codex`) が label に応じて選ばれる
- PR mention agent:
  repo variable `VIRTUAL_TEAM_PR_AGENT_MENTION`
  未設定時は `@copilot`

GitHub native route は `auto` / `copilot` / `claude` / `codex` を扱う。`Gemini` は local runner (`runtime:task -- ai --provider gemini`) を正規 route とする。
`auto` は capability policy で `Claude` / `Codex` / native default を選ぶ。

GitHub-hosted kickoff は `VIRTUAL_TEAM_GH_USER_TOKEN` を優先し、runner 上で `gh auth login --with-token` してから native task を起動する。現在の repo ではこれを既定にしている。

## API fallback

vendor CLI / API ベースの workflow へ戻すこと自体は可能だが、既定ルートではない。  
この repo は subscription-native agents を正規ルートとして扱う。

## 運用の基本形

1. issue を作る
2. `auto` `copilot` `claude` `codex` のいずれかを付ける
3. local planner が atomic 判定または sub-issue 分解を返す
4. atomic issue には coding-agent label が付き、GitHub Actions が subscription-native coding agent task を自動起動する
5. kickoff 後、watchdog が open な native agent PR を検出し、commit が落ち着いたあと `agent-pr-verify` を自動 dispatch する
6. `agent-pr-verify` が verify / review handoff / impact comment をまとめて実行する
7. review / checks が揃えば auto-merge を試みる
8. 定期 maintenance と weekly reindex が裏側の health を保つ

## 必須前提

native route 自体は vendor API secret 不要。  
ただし GitHub Actions から user-authenticated に起動するため、`VIRTUAL_TEAM_GH_USER_TOKEN` は必須である。未設定なら kickoff workflow は失敗する。

## いまの境界

- GitHub 上の generic AI pipeline はこの文書の workflow で扱う
- `runtime:task -- ai --provider claude|codex|gemini ...` は local runner
- Cloudflare deploy、LINE CRM 固有 rule、product-specific preview は吸収対象外
