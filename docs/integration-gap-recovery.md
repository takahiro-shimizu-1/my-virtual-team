# Integration Gap Recovery

## 目的

`my-virtual-team` は `agent-skill-bus`、`gitnexus-stable-ops`、`line-harness-oss` を吸収する前提だったが、v4 では一部の一般化可能な機能まで削ってしまった。  
この文書は「各 source repo のうち、固有機能ではないのに未吸収なもの」を明示し、回復対象を固定する。

## 判断基準

- 吸収する: 他の product / domain でも使える一般機能
- 吸収しない: LINE CRM、Cloudflare deploy、特定 product の business rule に強く結びつくもの

## Gap Matrix

| Source | 機能 | 現状 | 判断 |
|---|---|---|---|
| `agent-skill-bus` | durable queue / DAG / lock / run logging | 吸収済み | 維持 |
| `agent-skill-bus` | knowledge watcher | 部分吸収 | 外部 watcher と改善 loop を追加 |
| `agent-skill-bus` | self-improving skills | 部分吸収 | trend / enqueue 済み、scheduled loop を追加 |
| `gitnexus-stable-ops` | workspace / graph builder / resolver / MCP | 吸収済み | 維持 |
| `gitnexus-stable-ops` | doctor / smoke test / auto-reindex hooks | 今回追加 | 維持 |
| `gitnexus-stable-ops` | CI impact / post-merge reindex workflow | 未吸収 | 吸収対象 |
| `line-harness-oss` | event bus / health / runbook / watcher | 吸収済み | 維持 |
| `line-harness-oss` | GitHub issue / PR bridge | 部分吸収 | route / plan / close から拡張 |
| `line-harness-oss` | Claude decompose pipeline | 部分吸収 | workflow 追加、live secret 検証が残り |
| `line-harness-oss` | Claude AI review pipeline | 部分吸収 | workflow 追加、live secret 検証が残り |
| `line-harness-oss` | auto-merge pipeline | 部分吸収 | workflow 追加、live PR 検証が残り |
| `line-harness-oss` | Copilot watchdog | 部分吸収 | workflow 追加、live rerun 検証が残り |
| `line-harness-oss` | Cloudflare deploy / preview | 未吸収 | domain-specific のため対象外 |
| `line-harness-oss` | LINE CRM domain rules | 未吸収 | domain-specific のため対象外 |

## 直近で戻すもの

### 1. GitNexus Ops

- `graph:doctor`
- `graph:smoke`
- `graph:install-hooks`
- GitHub Actions の post-merge reindex
- GitHub Actions の PR impact comment

### 2. Claude on GitHub

- issue labeled で Claude が atomic / decomposition を判定
- PR opened / synchronize で Claude review
- review / CI success 後の auto-merge
- Copilot `action_required` を再実行する watchdog

### 3. Agent Skill Self-Improve

- `skill_runs` から trend / drift を集計
- degraded skill を `improvement task` として durable runtime へ enqueue
- knowledge watcher と skill health を接続

## 完了条件

- 3 source repo の「一般化可能な機能」が `my-virtual-team` に実装されている
- 削るのは domain-specific なものだけと明文化されている
- GitHub 上の AI pipeline が `route / plan / close` だけで止まらない
