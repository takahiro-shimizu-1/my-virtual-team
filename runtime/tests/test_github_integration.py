from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SRC_ROOT / "integrations") not in sys.path:
    sys.path.insert(0, str(SRC_ROOT / "integrations"))

import github_ops


def load_bridge_module():
    script_path = REPO_ROOT / "scripts" / "github-event-bridge.py"
    spec = importlib.util.spec_from_file_location("github_event_bridge", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class GitHubIntegrationTests(unittest.TestCase):
    def test_resolve_repository_prefers_explicit_env(self) -> None:
        repo = github_ops.resolve_repository(
            env={"VIRTUAL_TEAM_GITHUB_REPOSITORY": "example-org/example-repo"}
        )
        self.assertEqual(repo, "example-org/example-repo")

    def test_has_notification_target_reads_nested_payload(self) -> None:
        payload = {
            "task": {
                "payload": {
                    "github": {
                        "repo": "example-org/example-repo",
                        "issue_number": 42,
                    }
                }
            }
        }
        self.assertTrue(github_ops.has_notification_target(payload))

    def test_deliver_notification_comments_and_closes_issue(self) -> None:
        notification = {
            "payload": {
                "event": {
                    "event_type": "task.completed",
                    "payload": {},
                },
                "task": {
                    "task_id": "task-123",
                    "title": "API design review",
                    "status": "completed",
                    "agent_id": "kirishima-ren",
                    "workflow_id": "wf-123",
                    "source": "github",
                    "payload": {
                        "github": {
                            "repo": "example-org/example-repo",
                            "issue_number": 42,
                            "close_on_complete": True,
                        }
                    },
                    "outputs": [{"path": "outputs/review.md", "kind": "artifact"}],
                },
                "agent": {"name": "桐島 蓮"},
            }
        }
        with patch.object(
            github_ops,
            "add_comment",
            return_value={
                "status": "commented",
                "external_id": "comment-1",
                "target_kind": "issue",
                "target_number": 42,
            },
        ) as add_comment, patch.object(
            github_ops,
            "close_issue",
            return_value={"status": "closed", "issue_number": 42},
        ) as close_issue:
            result = github_ops.deliver_notification(notification)

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["external_id"], "comment-1")
        self.assertEqual(result["close_result"]["status"], "closed")
        add_comment.assert_called_once()
        close_issue.assert_called_once_with(issue_number=42, repo="example-org/example-repo")

    def test_bridge_routes_issue_comment_in_dry_run(self) -> None:
        bridge = load_bridge_module()
        event = {
            "repository": {"full_name": "example-org/example-repo"},
            "issue": {
                "number": 7,
                "title": "API設計レビューをお願いします",
                "body": "既存APIの認可設計を見直したいです。",
            },
            "comment": {
                "body": "/vt route",
                "author_association": "MEMBER",
            },
            "sender": {"login": "octocat"},
        }
        result = bridge.handle_event("issue_comment", event, dry_run=True)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["action"], "route")
        self.assertEqual(result["comment"]["status"], "dry_run")


if __name__ == "__main__":
    unittest.main()
