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
| `agent-skill-bus` | knowledge watcher | 吸収済み | watcher と knowledge-driven revalidation task を接続 |
| `agent-skill-bus` | self-improving skills | 吸収済み | trend / drift / scheduled maintenance loop まで実装 |
| `gitnexus-stable-ops` | workspace / graph builder / resolver / MCP | 吸収済み | 維持 |
| `gitnexus-stable-ops` | doctor / smoke test / auto-reindex hooks | 今回追加 | 維持 |
| `gitnexus-stable-ops` | CI impact / post-merge reindex workflow | 吸収済み | workflow と impact report を追加 |
| `gitnexus-stable-ops` | weekly full reindex | 吸収済み | `gitnexus-weekly.yml` を追加 |
| `line-harness-oss` | event bus / health / runbook / watcher | 吸収済み | 維持 |
| `line-harness-oss` | GitHub issue / PR bridge | 吸収済み | route / plan / close / issue assign / PR comment まで統合 |
| `line-harness-oss` | Claude decompose pipeline | 吸収済み | native-first planner に置換し、subscription route を既定化 |
| `line-harness-oss` | Claude AI review pipeline | 吸収済み | native agent mention route に置換し、subscription route を既定化 |
| `line-harness-oss` | auto-merge pipeline | 吸収済み | workflow 実装済み |
| `line-harness-oss` | Copilot watchdog | 吸収済み | workflow 実装済み |
| `line-harness-oss` | Cloudflare deploy / preview | 未吸収 | domain-specific のため対象外 |
| `line-harness-oss` | LINE CRM domain rules | 未吸収 | domain-specific のため対象外 |

## 直近で戻すもの

### 1. GitNexus Ops

- [x] `graph:doctor`
- [x] `graph:smoke`
- [x] `graph:install-hooks`
- [x] GitHub Actions の post-merge reindex
- [x] GitHub Actions の PR impact comment
- [x] GitHub Actions の weekly full reindex

### 2. Claude on GitHub

- [x] issue labeled で Claude が atomic / decomposition を判定
- [x] managed AI PR verify 成功後に Claude review handoff
- [x] review / CI success 後の auto-merge
- [x] Copilot `action_required` を再実行する watchdog

### 3. Agent Skill Self-Improve

- [x] `skill_runs` から trend / drift を集計
- [x] degraded skill を `improvement task` として durable runtime へ enqueue
- [x] knowledge watcher と skill health を接続
- [x] scheduled maintenance loop で watcher / self-improve / health を定期実行

## 完了条件

- 3 source repo の「一般化可能な機能」が `my-virtual-team` に実装されている
- 削るのは domain-specific なものだけと明文化されている
- GitHub 上の AI pipeline が `route / plan / close` だけで止まらない
- GitHub 上の AI workflow が subscription-native agents を既定ルートにしている
