from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def load_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "github-agent-task.py"
    spec = importlib.util.spec_from_file_location("github_agent_task_script", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GitHubAgentTaskScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_resolve_claude_label_to_custom_agent(self) -> None:
        agent, source = self.module._resolve_issue_custom_agent({"labels": [{"name": "claude"}]}, "API設計レビュー")
        self.assertEqual(agent, "vt-implementation-claude")
        self.assertEqual(source, "issue-label")

    def test_resolve_codex_label_to_custom_agent(self) -> None:
        agent, source = self.module._resolve_issue_custom_agent({"labels": [{"name": "codex"}]}, "READMEを直す")
        self.assertEqual(agent, "vt-implementation-codex")
        self.assertEqual(source, "issue-label")

    def test_resolve_gemini_label_raises_clear_error(self) -> None:
        with self.assertRaises(RuntimeError) as context:
            self.module._resolve_issue_custom_agent({"labels": [{"name": "gemini"}]}, "競合調査レポート")
        self.assertIn("Gemini", str(context.exception))

    def test_auto_label_uses_capability_policy_for_planning(self) -> None:
        agent, source = self.module._resolve_issue_custom_agent(
            {"labels": [{"name": "auto"}]},
            "API設計レビューをお願いします",
        )
        self.assertEqual(agent, "vt-implementation-claude")
        self.assertEqual(source, "capability-policy")

    def test_auto_label_uses_capability_policy_for_simple_implementation(self) -> None:
        agent, source = self.module._resolve_issue_custom_agent(
            {"labels": [{"name": "auto"}]},
            "README.md に quickstart を追加して",
        )
        self.assertEqual(agent, "vt-implementation-auto")
        self.assertEqual(source, "capability-policy")

    def test_prompt_mode_uses_capability_policy_for_planning(self) -> None:
        recommendation = self.module.recommend_execution(prompt="API設計レビューをお願いします")
        self.assertEqual(recommendation["github_profile"], "vt-implementation-claude")
