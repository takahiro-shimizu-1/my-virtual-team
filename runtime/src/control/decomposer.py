from __future__ import annotations

import re

from control.execution_policy import recommend_execution
from control.router import context_for_agent, route_request
from registry.catalog import get_agent


def _contains(prompt: str, *keywords: str) -> bool:
    return any(keyword.lower() in prompt.lower() for keyword in keywords)


def _sequential(prompt: str) -> bool:
    return bool(re.search(r"(その後|次に|してから|後で|レビュー|確認)", prompt))


def _phase_spec(
    *,
    agent_id: str,
    title: str,
    description: str,
    request: str,
    command: str,
    workflow_name: str,
    skill_id: str,
    required_context: list[str],
    depends_on_indexes: list[int],
    approval_required: bool = False,
    approval_note: str = "",
    review_mode: bool = False,
) -> dict:
    agent = get_agent(agent_id) or {}
    execution_recommendation = recommend_execution(
        prompt=request,
        command=command,
        matched_skill=skill_id,
        workflow_name=workflow_name,
        review_mode=review_mode,
        approval_required=approval_required,
        approval_policy=agent.get("approval_policy", ""),
    )
    return {
        "agent_id": agent_id,
        "title": title,
        "description": description,
        "task_mode": agent.get("execution_mode", "tracked_fast_path"),
        "depends_on_indexes": depends_on_indexes,
        "approval_required": approval_required,
        "approval_note": approval_note,
        "affected_skills": [skill_id] if skill_id else [],
        "payload": {
            "request": request,
            "department_command": command,
            "workflow_name": workflow_name,
            "skill_id": skill_id or f"agent:{agent_id}",
            "required_context": required_context,
            "review_mode": review_mode,
            "execution_recommendation": execution_recommendation,
        },
    }


def _build_api_review_workflow(prompt: str, command: str, route: dict) -> dict:
    owner = route["owner"]["agent_id"]
    reviewer = "kujo-haru" if owner == "kirishima-ren" else "kirishima-ren"
    skill_id = (route.get("matched_skill") or {}).get("name", "api-design-review")
    approval_note = "主要設計変更に当たる場合のみ chief approval を挟む"
    phases = [
        _phase_spec(
            agent_id=owner,
            title="API設計ドラフトを作る",
            description=prompt,
            request=prompt,
            command=command,
            workflow_name="api-design-review",
            skill_id=skill_id,
            required_context=context_for_agent(owner, skill_id),
            depends_on_indexes=[],
        ),
        _phase_spec(
            agent_id=reviewer,
            title="API設計レビューを行う",
            description=f"前段のドラフトをレビューする: {prompt}",
            request=prompt,
            command=command,
            workflow_name="api-design-review",
            skill_id=skill_id,
            required_context=context_for_agent(reviewer, skill_id),
            depends_on_indexes=[0],
            approval_required=route["approval_required"],
            approval_note=approval_note,
            review_mode=True,
        ),
    ]
    return {"workflow_name": "api-design-review", "phases": phases}


def _build_sequential_workflow(prompt: str, command: str, route: dict, agents: list[str], workflow_name: str) -> dict:
    skill_id = (route.get("matched_skill") or {}).get("name", workflow_name)
    phases = []
    for index, agent_id in enumerate(agents):
        phases.append(
            _phase_spec(
                agent_id=agent_id,
                title=f"{get_agent(agent_id)['name']} の担当フェーズ",
                description=prompt if index == 0 else f"前段成果物を引き継いで進める: {prompt}",
                request=prompt,
                command=command,
                workflow_name=workflow_name,
                skill_id=skill_id,
                required_context=context_for_agent(agent_id, skill_id),
                depends_on_indexes=[index - 1] if index > 0 else [],
                approval_required=route["approval_required"] if index == len(agents) - 1 else False,
                approval_note=f"{route['approval_policy']} に従い最終段で確認する" if index == len(agents) - 1 else "",
            )
        )
    return {"workflow_name": workflow_name, "phases": phases}


def decompose_request(prompt: str, command: str | None = None) -> dict:
    route = route_request(prompt, command)
    if not route.get("owner"):
        raise RuntimeError("owner agent could not be resolved")

    normalized_command = route.get("command", "")
    owner_id = route["owner"]["agent_id"]
    matched_skill = (route.get("matched_skill") or {}).get("name", "")
    collaborator_ids = [agent["agent_id"] for agent in route.get("collaborators", [])]

    if matched_skill == "api-design-review":
        workflow = _build_api_review_workflow(prompt, normalized_command, route)
    elif _contains(prompt, "提案", "見積") and _contains(prompt, "要件", "ヒアリング"):
        workflow = _build_sequential_workflow(
            prompt,
            normalized_command,
            route,
            ["horie-ryo", "mizuno-akari"],
            "proposal-to-requirements",
        )
    elif _contains(prompt, "要件", "要件定義", "requirements") and _contains(prompt, "実装", "開発", "API", "Web"):
        workflow = _build_sequential_workflow(
            prompt,
            normalized_command,
            route,
            ["mizuno-akari", "kirishima-ren"],
            "requirements-to-implementation",
        )
    elif _contains(prompt, "AI", "LLM", "RAG", "エージェント") and _contains(prompt, "Web", "アプリ", "API", "実装"):
        workflow = _build_sequential_workflow(
            prompt,
            normalized_command,
            route,
            ["kujo-haru", "kirishima-ren"],
            "ai-design-to-implementation",
        )
    elif matched_skill == "x-post-context" and _contains(prompt, "レビュー", "確認", "セルフレビュー"):
        workflow = _build_sequential_workflow(
            prompt,
            normalized_command,
            route,
            ["asahina-yu", "asahina-yu"],
            "content-draft-review",
        )
    elif collaborator_ids and _sequential(prompt):
        workflow = _build_sequential_workflow(
            prompt,
            normalized_command,
            route,
            [owner_id, *collaborator_ids],
            "multi-agent-handoff",
        )
    else:
        skill_id = matched_skill or f"agent:{owner_id}"
        workflow = {
            "workflow_name": "single-agent-fast-path",
            "phases": [
                _phase_spec(
                    agent_id=owner_id,
                    title=route["owner"]["name"],
                    description=prompt,
                    request=prompt,
                    command=normalized_command,
                    workflow_name="single-agent-fast-path",
                    skill_id=skill_id,
                    required_context=context_for_agent(owner_id, matched_skill or None),
                    depends_on_indexes=[],
                    approval_required=route["approval_required"],
                    approval_note=f"{route['approval_policy']} に従って確認する" if route["approval_required"] else "",
                )
            ],
        }

    return {
        "route": route,
        "workflow_name": workflow["workflow_name"],
        "tasks": workflow["phases"],
    }
