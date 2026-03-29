from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from registry.catalog import load_agents_registry


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _direct_agents(changed_files: list[str]) -> list[dict]:
    agents = []
    for agent in load_agents_registry():
        file_path = agent.get("file", "")
        if file_path and file_path in changed_files:
            agents.append(
                {
                    "agent_id": agent["agent_id"],
                    "name": agent.get("name", agent["agent_id"]),
                    "file": file_path,
                    "department": agent.get("department", ""),
                }
            )
    return agents


def _candidate_paths(changed_files: list[str]) -> list[str]:
    candidates = set(changed_files)
    for path in changed_files:
        if path.startswith(("docs/", "guidelines/", "templates/", ".claude/rules/", ".claude/commands/")):
            candidates.add(f".gitnexus/knowledge/{path}")
        if path == "AGENTS_CLAUDE.md":
            candidates.add(".gitnexus/knowledge/AGENTS_CLAUDE.md")
    return sorted(candidates)


def _query_nodes(conn: sqlite3.Connection, table: str, id_col: str, name_col: str, changed_files: list[str]) -> list[dict]:
    if not changed_files:
        return []
    placeholders = ",".join("?" for _ in changed_files)
    rows = conn.execute(
        f"SELECT {id_col} AS node_id, {name_col} AS name, path FROM {table} WHERE path IN ({placeholders}) ORDER BY {id_col}",
        tuple(changed_files),
    ).fetchall()
    return [{"node_id": row["node_id"], "name": row["name"], "path": row["path"]} for row in rows]


def _agent_info(conn: sqlite3.Connection, agent_id: str) -> dict | None:
    row = conn.execute("SELECT agent_id, name, role, society FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    if not row:
        return None
    return {"agent_id": row["agent_id"], "name": row["name"], "role": row["role"], "society": row["society"]}


def _skill_info(conn: sqlite3.Connection, skill_id: str) -> dict | None:
    row = conn.execute("SELECT skill_id, name, category, path FROM skills WHERE skill_id = ?", (skill_id,)).fetchone()
    if not row:
        return None
    return {"skill_id": row["skill_id"], "name": row["name"], "category": row["category"], "path": row["path"]}


def _doc_info(conn: sqlite3.Connection, doc_id: str) -> dict | None:
    row = conn.execute("SELECT doc_id, title, path, category FROM knowledge_docs WHERE doc_id = ?", (doc_id,)).fetchone()
    if not row:
        return None
    return {"doc_id": row["doc_id"], "title": row["title"], "path": row["path"], "category": row["category"]}


def _direct_impact(conn: sqlite3.Connection, changed_files: list[str]) -> dict:
    candidate_paths = _candidate_paths(changed_files)
    return {
        "agents": _direct_agents(changed_files),
        "skills": _query_nodes(conn, "skills", "skill_id", "name", candidate_paths),
        "docs": _query_nodes(conn, "knowledge_docs", "doc_id", "title", candidate_paths),
    }


def _expand_from_agents(conn: sqlite3.Connection, agent_ids: list[str]) -> tuple[list[dict], list[dict]]:
    skills = {}
    docs = {}
    for agent_id in agent_ids:
        rows = conn.execute(
            """
            SELECT target_id
            FROM agent_relations
            WHERE source_id = ? AND source_type = 'Agent' AND relation_type = 'USES_SKILL'
            """,
            (agent_id,),
        ).fetchall()
        for row in rows:
            skill = _skill_info(conn, row["target_id"])
            if skill:
                skills[skill["skill_id"]] = skill
                dep_rows = conn.execute(
                    """
                    SELECT target_id
                    FROM agent_relations
                    WHERE source_id = ? AND source_type = 'Skill' AND relation_type = 'DEPENDS_ON'
                    """,
                    (skill["skill_id"],),
                ).fetchall()
                for dep in dep_rows:
                    doc = _doc_info(conn, dep["target_id"])
                    if doc:
                        docs[doc["doc_id"]] = doc
    return list(skills.values()), list(docs.values())


def _expand_from_skills(conn: sqlite3.Connection, skill_ids: list[str]) -> tuple[list[dict], list[dict]]:
    agents = {}
    docs = {}
    for skill_id in skill_ids:
        rows = conn.execute(
            """
            SELECT source_id
            FROM agent_relations
            WHERE target_id = ? AND target_type = 'Skill' AND relation_type = 'USES_SKILL'
            """,
            (skill_id,),
        ).fetchall()
        for row in rows:
            agent = _agent_info(conn, row["source_id"])
            if agent:
                agents[agent["agent_id"]] = agent
        dep_rows = conn.execute(
            """
            SELECT target_id
            FROM agent_relations
            WHERE source_id = ? AND source_type = 'Skill' AND relation_type = 'DEPENDS_ON'
            """,
            (skill_id,),
        ).fetchall()
        for dep in dep_rows:
            doc = _doc_info(conn, dep["target_id"])
            if doc:
                docs[doc["doc_id"]] = doc
    return list(agents.values()), list(docs.values())


def _expand_from_docs(conn: sqlite3.Connection, doc_ids: list[str]) -> tuple[list[dict], list[dict]]:
    skills = {}
    agents = {}
    for doc_id in doc_ids:
        rows = conn.execute(
            """
            SELECT source_id
            FROM agent_relations
            WHERE target_id = ? AND target_type = 'KnowledgeDoc' AND relation_type = 'DEPENDS_ON'
            """,
            (doc_id,),
        ).fetchall()
        for row in rows:
            skill = _skill_info(conn, row["source_id"])
            if skill:
                skills[skill["skill_id"]] = skill
                agent_rows = conn.execute(
                    """
                    SELECT source_id
                    FROM agent_relations
                    WHERE target_id = ? AND target_type = 'Skill' AND relation_type = 'USES_SKILL'
                    """,
                    (skill["skill_id"],),
                ).fetchall()
                for agent_row in agent_rows:
                    agent = _agent_info(conn, agent_row["source_id"])
                    if agent:
                        agents[agent["agent_id"]] = agent
    return list(skills.values()), list(agents.values())


def _risk_level(report: dict) -> str:
    score = 0
    score += len(report["direct"]["agents"]) * 3
    score += len(report["direct"]["skills"]) * 2
    score += len(report["direct"]["docs"])
    score += len(report["affected"]["agents"]) * 2
    score += len(report["affected"]["skills"]) * 2
    if score >= 10:
        return "high"
    if score >= 5:
        return "medium"
    return "low"


def build_impact_report(repo_root: Path, db_path: Path, changed_files: list[str]) -> dict:
    conn = _connect(db_path)
    try:
        direct = _direct_impact(conn, changed_files)

        affected_agents = {item["agent_id"]: item for item in direct["agents"]}
        affected_skills = {item["node_id"]: {"skill_id": item["node_id"], "name": item["name"], "path": item["path"]} for item in direct["skills"]}
        affected_docs = {item["node_id"]: {"doc_id": item["node_id"], "title": item["name"], "path": item["path"]} for item in direct["docs"]}

        skill_hits, doc_hits = _expand_from_agents(conn, list(affected_agents.keys()))
        for skill in skill_hits:
            affected_skills[skill["skill_id"]] = skill
        for doc in doc_hits:
            affected_docs[doc["doc_id"]] = doc

        agent_hits, doc_hits = _expand_from_skills(conn, list(affected_skills.keys()))
        for agent in agent_hits:
            affected_agents[agent["agent_id"]] = agent
        for doc in doc_hits:
            affected_docs[doc["doc_id"]] = doc

        skill_hits, agent_hits = _expand_from_docs(conn, list(affected_docs.keys()))
        for skill in skill_hits:
            affected_skills[skill["skill_id"]] = skill
        for agent in agent_hits:
            affected_agents[agent["agent_id"]] = agent

        report = {
            "status": "ok",
            "changed_files": changed_files,
            "direct": direct,
            "affected": {
                "agents": sorted(affected_agents.values(), key=lambda item: item.get("agent_id", "")),
                "skills": sorted(affected_skills.values(), key=lambda item: item.get("skill_id", "")),
                "docs": sorted(affected_docs.values(), key=lambda item: item.get("path", "")),
            },
        }
        report["risk_level"] = _risk_level(report)
        return report
    finally:
        conn.close()


def render_markdown(report: dict) -> str:
    def fmt_agents(items: list[dict]) -> list[str]:
        return [f"- {item.get('name', item.get('agent_id', ''))} (`{item.get('agent_id', '')}`)" for item in items] or ["- none"]

    def fmt_skills(items: list[dict]) -> list[str]:
        return [f"- `{item.get('skill_id', item.get('node_id', ''))}` {item.get('name', '')}" for item in items] or ["- none"]

    def fmt_docs(items: list[dict]) -> list[str]:
        return [f"- `{item.get('path', '')}`" for item in items] or ["- none"]

    lines = [
        "## GitNexus Impact Report",
        "",
        f"- risk_level: `{report['risk_level']}`",
        f"- changed_files: `{len(report['changed_files'])}`",
        "",
        "**Directly Changed Agents**",
        *fmt_agents(report["direct"]["agents"]),
        "",
        "**Directly Changed Skills**",
        *fmt_skills(report["direct"]["skills"]),
        "",
        "**Directly Changed Docs**",
        *fmt_docs(report["direct"]["docs"]),
        "",
        "**Affected Agents**",
        *fmt_agents(report["affected"]["agents"]),
        "",
        "**Affected Skills**",
        *fmt_skills(report["affected"]["skills"]),
        "",
        "**Affected Docs**",
        *fmt_docs(report["affected"]["docs"]),
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight GitNexus impact report for changed files")
    parser.add_argument("files", nargs="*", help="Changed files")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--stdin", action="store_true", help="Read changed files from stdin")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo.resolve()
    db_path = args.db or (repo_root / ".gitnexus" / "agent-graph.db")

    changed_files = [file for file in args.files if file]
    if args.stdin:
        changed_files.extend([line.strip() for line in sys.stdin if line.strip()])
    changed_files = sorted(dict.fromkeys(changed_files))

    report = build_impact_report(repo_root, db_path, changed_files)
    if args.markdown:
        print(render_markdown(report))
    elif args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
