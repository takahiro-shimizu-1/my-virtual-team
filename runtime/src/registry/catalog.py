from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_DIR = REPO_ROOT / "registry"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_agents_registry() -> list[dict]:
    data = _load_json(REGISTRY_DIR / "agents.generated.json")
    return data.get("agents", [])


@lru_cache(maxsize=1)
def load_context_policy() -> dict:
    return _load_json(REGISTRY_DIR / "context-policy.generated.json")


@lru_cache(maxsize=1)
def load_skills_registry() -> list[dict]:
    data = _load_json(REGISTRY_DIR / "skills.generated.json")
    return data.get("skills", [])


def clear_registry_cache() -> None:
    load_agents_registry.cache_clear()
    load_context_policy.cache_clear()
    load_skills_registry.cache_clear()


def get_agent(agent_id: str) -> dict | None:
    for agent in load_agents_registry():
        if agent["agent_id"] == agent_id:
            return agent
    return None


def get_skill(skill_name: str) -> dict | None:
    for skill in load_skills_registry():
        if skill["name"] == skill_name:
            return skill
    return None


def normalize_command(command: str | None) -> str:
    if not command:
        return ""
    return command.strip().lstrip("/").lower()


def department_for_command(command: str | None) -> str:
    mapping = {
        "strategy": "01-strategy",
        "development": "02-development",
        "marketing": "03-marketing",
        "research": "04-research",
        "admin": "05-admin",
    }
    return mapping.get(normalize_command(command), "")


def guideline_path_from_slug(slug: str) -> str:
    policy = load_context_policy()
    guideline = policy.get("guidelines", {}).get(slug, {})
    return guideline.get("path", "")

