from __future__ import annotations

from registry.catalog import normalize_command

SECURITY_KEYWORDS = [
    "security",
    "secret",
    "credential",
    "auth",
    "認証",
    "認可",
    "シークレット",
    "機密",
    "脆弱性",
    "権限",
    "workflow",
    ".github/workflows",
]
LEGAL_FINANCE_KEYWORDS = [
    "請求",
    "契約",
    "法務",
    "経理",
    "税務",
    "invoice",
    "billing",
    "legal",
    "finance",
]
PLANNING_KEYWORDS = [
    "計画",
    "plan",
    "設計",
    "architecture",
    "アーキテクチャ",
    "要件",
    "requirements",
    "提案",
    "strategy",
    "roadmap",
    "レビュー",
    "review",
]
RESEARCH_KEYWORDS = [
    "research",
    "調査",
    "競合",
    "市場",
    "レポート",
    "report",
    "比較",
    "survey",
    "benchmark",
]
LARGE_CHANGE_KEYWORDS = [
    "refactor",
    "migration",
    "rename",
    "extract",
    "split",
    "一括",
    "大量",
    "全ファイル",
    "全",
    "移行",
    "リファクタ",
]
IMPLEMENTATION_KEYWORDS = [
    "fix",
    "bug",
    "修正",
    "実装",
    "追加",
    "feat",
    "feature",
    "test",
    "テスト",
    "README",
    "docs",
    "document",
]
CONTENT_KEYWORDS = [
    "x投稿",
    "投稿",
    "note",
    "記事",
    "ブログ",
    "コンテンツ",
    "コピー",
]


def _contains(prompt: str, keywords: list[str]) -> list[str]:
    lowered = (prompt or "").lower()
    return [keyword for keyword in keywords if keyword.lower() in lowered]


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def recommend_execution(
    *,
    prompt: str,
    command: str | None = None,
    matched_skill: str = "",
    workflow_name: str = "single-agent-fast-path",
    review_mode: bool = False,
    approval_required: bool = False,
    approval_policy: str = "",
) -> dict:
    normalized_command = normalize_command(command)
    planning_hits = _contains(prompt, PLANNING_KEYWORDS)
    security_hits = _contains(prompt, SECURITY_KEYWORDS)
    research_hits = _contains(prompt, RESEARCH_KEYWORDS)
    large_hits = _contains(prompt, LARGE_CHANGE_KEYWORDS)
    implementation_hits = _contains(prompt, IMPLEMENTATION_KEYWORDS)
    content_hits = _contains(prompt, CONTENT_KEYWORDS)

    capability_tier = "standard"
    intent = "implementation"
    preferred_surface = "github-native"
    github_label = "auto"
    github_profile = "vt-implementation-auto"
    local_provider = "codex"
    local_fallback_providers = ["claude"]
    reasons: list[str] = []

    if normalized_command in {"research"} or research_hits:
        capability_tier = "deep"
        intent = "research"
        preferred_surface = "local"
        github_label = "claude"
        github_profile = "vt-implementation-claude"
        local_provider = "gemini"
        local_fallback_providers = ["claude", "codex"]
        reasons.append("research-heavy")

    elif (
        normalized_command in {"strategy"}
        or review_mode
        or workflow_name != "single-agent-fast-path"
        or matched_skill == "api-design-review"
        or planning_hits
    ):
        capability_tier = "deep"
        intent = "planning"
        preferred_surface = "local"
        github_label = "claude"
        github_profile = "vt-implementation-claude"
        local_provider = "claude"
        local_fallback_providers = ["codex"]
        reasons.append("planning-or-review")

    elif security_hits or (approval_policy == "financial_or_legal_decision" and _contains(prompt, LEGAL_FINANCE_KEYWORDS)):
        capability_tier = "deep"
        intent = "sensitive"
        preferred_surface = "local"
        github_label = "claude"
        github_profile = "vt-implementation-claude"
        local_provider = "claude"
        local_fallback_providers = ["codex"]
        reasons.append("security-or-sensitive")

    elif large_hits:
        capability_tier = "high-code"
        intent = "refactor"
        preferred_surface = "local"
        github_label = "codex"
        github_profile = "vt-implementation-codex"
        local_provider = "codex"
        local_fallback_providers = ["claude"]
        reasons.append("large-code-change")

    elif normalized_command == "marketing" or content_hits:
        capability_tier = "high-touch"
        intent = "content"
        preferred_surface = "local"
        github_label = "claude"
        github_profile = "vt-implementation-claude"
        local_provider = "claude"
        local_fallback_providers = ["gemini", "codex"]
        reasons.append("content-quality")

    elif implementation_hits or normalized_command in {"development", "admin"}:
        capability_tier = "standard"
        intent = "implementation"
        preferred_surface = "github-native"
        github_label = "auto"
        github_profile = "vt-implementation-auto"
        local_provider = "codex"
        local_fallback_providers = ["claude"]
        reasons.append("single-task-implementation")

    if approval_required and "approval-required" not in reasons:
        reasons.append("approval-required")
    if matched_skill:
        reasons.append(f"skill:{matched_skill}")
    if normalized_command:
        reasons.append(f"command:{normalized_command}")

    return {
        "capability_tier": capability_tier,
        "intent": intent,
        "preferred_surface": preferred_surface,
        "github_label": github_label,
        "github_profile": github_profile,
        "local_provider": local_provider,
        "local_fallback_providers": _dedupe(local_fallback_providers),
        "reasons": _dedupe(reasons),
        "source": "capability-policy-v1",
    }
