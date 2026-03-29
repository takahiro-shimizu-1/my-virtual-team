from __future__ import annotations

from control.execution_policy import recommend_execution
from registry.catalog import (
    department_for_command,
    get_agent,
    guideline_path_from_slug,
    load_agents_registry,
    load_context_policy,
    load_skills_registry,
    normalize_command,
)

APPROVAL_HINTS = {
    "external_brand_risk": ["公開", "発信", "投稿", "SNS", "プレスリリース", "note", "YouTube"],
    "estimate_or_schedule_commit": ["提案", "見積", "ROI", "納期", "導入"],
    "major_architecture_change": ["アーキテクチャ", "基盤", "移行", "DB変更", "設計刷新"],
    "model_change_or_api_cost_impact": ["モデル", "LLM", "API費用", "課金", "プロンプト"],
    "scope_change_or_budget_impact": ["要件変更", "追加要件", "予算", "スコープ", "非機能要件"],
    "paid_research_or_sensitive_information": ["機密", "有料", "競合", "調査"],
    "financial_or_legal_decision": ["請求", "契約", "法務", "経理", "freee", "税務"],
    "major_direction_change": ["事業戦略", "方向性", "優先順位", "ロードマップ", "撤退"],
}


def _matches(text: str, keyword: str) -> bool:
    if not text or not keyword:
        return False
    return keyword.lower() in text.lower()


def _score_keywords(text: str, keywords: list[str], weight: int) -> tuple[int, list[str]]:
    score = 0
    matched = []
    for keyword in keywords:
        if _matches(text, keyword):
            score += weight
            matched.append(keyword)
    return score, matched


def _paths_for_agent(agent_id: str, skill_name: str | None = None) -> list[str]:
    policy = load_context_policy()
    agent_policy = policy.get("agents", {}).get(agent_id, {})
    paths = []
    for slug in agent_policy.get("always", []):
        path = guideline_path_from_slug(slug)
        if path:
            paths.append(path)

    if skill_name:
        for skill in load_skills_registry():
            if skill["name"] != skill_name:
                continue
            paths.extend(skill.get("depends_on", []))
            break

    deduped = []
    seen = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def route_request(prompt: str, command: str | None = None, top_n: int = 3) -> dict:
    normalized_command = normalize_command(command)
    preferred_department = department_for_command(normalized_command)

    skills = []
    for skill in load_skills_registry():
        score, matched = _score_keywords(prompt, skill.get("keywords", []), 10)
        if score <= 0:
            continue
        skills.append(
            {
                **skill,
                "score": score,
                "matched_keywords": matched,
            }
        )
    skills.sort(key=lambda item: (-item["score"], item["name"]))

    top_skill = skills[0] if skills else None
    top_skill_agents = set(top_skill.get("agents", [])) if top_skill else set()

    ranked_agents = []
    for agent in load_agents_registry():
        score, matched_keywords = _score_keywords(prompt, agent.get("keywords", []), 8)
        reasons = []

        if matched_keywords:
            reasons.append(f"keywords={','.join(matched_keywords)}")

        if preferred_department and agent.get("department") == preferred_department:
            score += 18
            reasons.append(f"command={normalized_command}")

        if agent["agent_id"] in top_skill_agents:
            score += 12
            reasons.append(f"skill={top_skill['name']}")

        if score <= 0:
            continue

        ranked_agents.append(
            {
                **agent,
                "score": score,
                "reasons": reasons,
            }
        )

    if not ranked_agents and preferred_department:
        ranked_agents = [
            {
                **agent,
                "score": 1,
                "reasons": [f"fallback-command={normalized_command}"],
            }
            for agent in load_agents_registry()
            if agent.get("department") == preferred_department
        ]

    ranked_agents.sort(key=lambda item: (-item["score"], item["agent_id"]))

    owner = ranked_agents[0] if ranked_agents else None
    collaborators = []
    if owner:
        collaborator_ids = set(top_skill_agents)
        for agent in ranked_agents[1:]:
            if agent["score"] >= max(8, owner["score"] * 0.5):
                collaborator_ids.add(agent["agent_id"])
        collaborator_ids.discard(owner["agent_id"])

        for agent_id in collaborator_ids:
            agent = get_agent(agent_id)
            if agent:
                collaborators.append(agent)
        collaborators.sort(key=lambda item: item["agent_id"])

    approval_required = False
    approval_keywords = APPROVAL_HINTS.get(owner["approval_policy"], []) if owner else []
    if owner and approval_keywords:
        approval_required = any(_matches(prompt, keyword) for keyword in approval_keywords)

    required_context = _paths_for_agent(owner["agent_id"], top_skill["name"] if top_skill else None) if owner else []
    execution_recommendation = (
        recommend_execution(
            prompt=prompt,
            command=normalized_command,
            matched_skill=top_skill["name"] if top_skill else "",
            workflow_name="single-agent-fast-path",
            approval_required=approval_required,
            approval_policy=owner["approval_policy"] if owner else "",
        )
        if owner
        else {}
    )

    return {
        "prompt": prompt,
        "command": normalized_command,
        "preferred_department": preferred_department,
        "matched_skill": top_skill,
        "matched_skills": skills[:top_n],
        "owner": owner,
        "collaborators": collaborators[:top_n],
        "required_context": required_context,
        "approval_required": approval_required,
        "approval_policy": owner["approval_policy"] if owner else "",
        "task_mode": owner["execution_mode"] if owner else "tracked_fast_path",
        "candidate_agents": ranked_agents[:top_n],
        "execution_recommendation": execution_recommendation,
    }


def context_for_agent(agent_id: str, skill_name: str | None = None) -> list[str]:
    return _paths_for_agent(agent_id, skill_name)
