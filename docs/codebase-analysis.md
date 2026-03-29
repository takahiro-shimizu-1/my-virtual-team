# Codebase Analysis (2026-03-29)

## Directory Structure
```
my-virtual-team/
├── CLAUDE.md                          # Chief orchestrator definition
├── agents/
│   ├── 01-strategy/
│   │   ├── tsurumin-seiichi.md        # 鶴見誠一 - ビジネス戦略
│   │   ├── mizuno-akari.md            # 水野あかり - 要件定義
│   │   └── horie-ryo.md              # 堀江遼 - 提案・見積
│   ├── 02-development/
│   │   ├── kirishima-ren.md           # 桐島蓮 - Web開発
│   │   └── kujo-haru.md              # 九条ハル - AI開発
│   ├── 03-marketing/
│   │   └── asahina-yu.md             # 朝比奈ユウ - SNSマーケ
│   ├── 04-research/
│   │   └── todo-rito.md              # 藤堂理人 - リサーチ
│   └── 05-admin/
│       └── komiya-sakura.md          # 小宮さくら - 経理・事務
├── guidelines/
│   ├── company-overview.md            # ~600 tokens
│   ├── brand-guidelines.md            # ~800 tokens
│   ├── output-standards.md            # ~500 tokens
│   ├── security-policy.md             # ~400 tokens
│   ├── escalation-rules.md            # ~500 tokens
│   ├── philosophy.md                  # ~1,200 tokens
│   └── top-posts-reference.md         # ~14,000 tokens (HUGE)
├── templates/
│   ├── invoice-memo.md
│   ├── proposal.md
│   ├── requirements-spec.md
│   ├── research-report.md
│   └── sns-post.md
├── .claude/
│   ├── commands/
│   │   ├── strategy.md                # /strategy ルーター
│   │   ├── development.md             # /development ルーター
│   │   ├── marketing.md               # /marketing ルーター
│   │   ├── research.md                # /research ルーター
│   │   └── admin.md                   # /admin ルーター
│   ├── rules/
│   │   ├── agent-launch.md            # 起動テンプレート
│   │   ├── context-reset.md           # コンテキストリセット
│   │   ├── evaluation-gate.md         # 品質ゲート
│   │   └── reporting-format.md        # レポート形式
│   └── skills/
│       └── review/
│           └── SKILL.md               # 振り返りスキル
└── .git/
```

## Agent Guidelines References (Current)
| Agent | References | Est. Tokens |
|-------|-----------|-------------|
| 鶴見誠一 | company-overview, brand-guidelines, output-standards, philosophy | ~3,100 |
| 水野あかり | company-overview, brand-guidelines, output-standards | ~1,900 |
| 堀江遼 | company-overview, brand-guidelines, output-standards, philosophy | ~3,100 |
| 桐島蓮 | company-overview, brand-guidelines, output-standards, security-policy | ~2,300 |
| 九条ハル | company-overview, brand-guidelines, output-standards, security-policy | ~2,300 |
| 朝比奈ユウ | company-overview, brand-guidelines, output-standards, philosophy, top-posts-reference | ~17,100 |
| 藤堂理人 | company-overview, brand-guidelines, output-standards, security-policy | ~2,300 |
| 小宮さくら | company-overview, brand-guidelines, output-standards, escalation-rules, security-policy | ~2,800 |

## Key Insight
朝比奈ユウ(マーケ)が~17Kトークンで突出。top-posts-reference.md(~14K)が主因。
他エージェントも brand-guidelines や philosophy を不要なのに読んでいるケースあり。
