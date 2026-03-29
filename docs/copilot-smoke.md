# Copilot Smoke Tests

## 概要

GitHub Issue / PR のイベントを `my-virtual-team` の仮想チームルーティングに通す smoke test の仕様まとめ。

---

## 検証内容

Smoke tests は以下を確認する。

| 対象 | 確認内容 |
|------|----------|
| Issue 作成 (`issues.opened`) | イベントを受信し、タイトル・本文からルーティングが決定される |
| Issue コメント (`issue_comment.created`) | コメント内のスラッシュコマンドが解釈・実行される |
| Synthetic Pull Request (`workflow_dispatch`) | 合成 PR payload で PR ルーティング分岐を dry-run 検証する |

いずれも `--dry-run` で実行され、実際の API 呼び出しや状態変更は行わない。

---

## 関連ワークフロー

### `validate` (`.github/workflows/validate.yml`)

- **トリガー**: `master` / `codex/**` / `copilot/**` / `claude/**` / `codex-agent/**` への push
- **役割**: `npm run ci:verify` を実行し、ブートストラップ・ユニットテスト・スモークテストを含む v4 契約全体を検証する
- **Smoke test の位置付け**: `ci:verify` の中で `scripts/github-event-bridge.py` を `--dry-run` で呼び出し、Issue / Issue コメント / synthetic PR の 3 シナリオを検証する

### `github-ops` (`.github/workflows/github-ops.yml`)

- **トリガー**: `codex/**` への push、`workflow_dispatch`、`issues`、`issue_comment`
- **役割**:
  - `bridge-live`: 本番 GitHub イベントを受けてルーティング・タスク登録を行う
  - `bridge-push-smoke`: push 時に合成イベントペイロードで 3 シナリオを `--dry-run` 検証する
  - `bridge-manual-smoke`: `workflow_dispatch` で任意のシナリオ・プロンプトを手動検証する

---

## サポートするスラッシュコマンド

Issue コメントまたは PR コメントで使用できる。

| コマンド | 説明 |
|---------|------|
| `/vt route` | 現在の Issue / PR のルーティング結果（owner・agent・skills・context）を表示する |
| `/vt plan` | マルチフェーズ分解プランを表示する（dry-run のみ、実行しない） |
| `/vt issue close` | Issue を close する（owner / member / collaborator のみ実行可能） |

`/vt route <任意テキスト>` や `/vt plan <任意テキスト>` のようにテキストを渡すと、Issue の内容の代わりにそのテキストでルーティング / プランニングを行う。
