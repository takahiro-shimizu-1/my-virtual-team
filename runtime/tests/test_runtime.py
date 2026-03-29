from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from control.runner_bridge import plan_request
from control.codex_runner import run_codex_task
from control.router import route_request
from control.skill_monitor import analyze_skill_health, enqueue_improvement_tasks
from control.task_store import complete_task, create_task, dispatch_ready_tasks, resolve_task_approval
from db.connection import connect_db
from db.migrate import apply_migrations
from events.bus import publish_pending_events
from health.aggregate import build_health_report
from watchers.local_files import scan_local_assets


class RuntimeFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "state.db"
        self.conn = connect_db(self.db_path)
        apply_migrations(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmpdir.cleanup()

    def test_route_resolves_api_review_skill(self) -> None:
        route = route_request("API設計レビューをお願いします", "development")
        self.assertEqual(route["matched_skill"]["name"], "api-design-review")
        self.assertIn(route["owner"]["agent_id"], {"kirishima-ren", "kujo-haru"})

    def test_plan_request_builds_sequential_workflow(self) -> None:
        planned = plan_request(
            self.conn,
            prompt="提案をまとめて、その後要件も整理して",
            command="strategy",
        )
        self.assertEqual(planned["workflow_name"], "proposal-to-requirements")
        self.assertEqual(len(planned["created_tasks"]), 2)
        first_task = planned["created_tasks"][0]
        second_task = planned["created_tasks"][1]
        self.assertEqual(second_task["dependencies"], [first_task["task_id"]])

    def test_approval_blocks_dispatch_until_resolved(self) -> None:
        task = create_task(
            self.conn,
            title="公開前レビュー",
            agent_id="asahina-yu",
            approval_required=True,
            approval_note="公開コンテンツのため",
        )
        self.assertEqual(dispatch_ready_tasks(self.conn), [])
        resolved = resolve_task_approval(self.conn, task["task_id"], "approved", note="chief ok")
        self.assertEqual(resolved["approvals"][-1]["decision"], "approved")
        dispatched = dispatch_ready_tasks(self.conn)
        self.assertEqual(dispatched[0]["task_id"], task["task_id"])

    def test_event_bus_creates_notifications_and_activity_log(self) -> None:
        task = create_task(
            self.conn,
            title="API設計レビュー",
            agent_id="kirishima-ren",
            payload={"skill_id": "api-design-review"},
        )
        dispatch_ready_tasks(self.conn)
        self.conn.execute(
            "UPDATE tasks SET status = 'claimed', current_attempt = 1, claimed_by = 'tester' WHERE task_id = ?",
            (task["task_id"],),
        )
        self.conn.execute(
            """
            INSERT INTO task_attempts (task_id, attempt_no, runner_id, status, started_at)
            VALUES (?, 1, 'tester', 'running', datetime('now'))
            """,
            (task["task_id"],),
        )
        self.conn.commit()
        complete_task(self.conn, task["task_id"], ["outputs/test.md"])
        result = publish_pending_events(self.conn, limit=20)
        self.assertGreaterEqual(result["count"], 1)
        notification_count = self.conn.execute("SELECT COUNT(*) AS count FROM notifications").fetchone()["count"]
        self.assertGreaterEqual(notification_count, 1)

    def test_event_bus_routes_github_for_linked_task(self) -> None:
        task = create_task(
            self.conn,
            title="Issue linked task",
            agent_id="kirishima-ren",
            payload={
                "skill_id": "api-design-review",
                "github": {
                    "repo": "example-org/example-repo",
                    "issue_number": 99,
                },
            },
        )
        dispatch_ready_tasks(self.conn)
        self.conn.execute(
            "UPDATE tasks SET status = 'claimed', current_attempt = 1, claimed_by = 'tester' WHERE task_id = ?",
            (task["task_id"],),
        )
        self.conn.execute(
            """
            INSERT INTO task_attempts (task_id, attempt_no, runner_id, status, started_at)
            VALUES (?, 1, 'tester', 'running', datetime('now'))
            """,
            (task["task_id"],),
        )
        self.conn.commit()
        complete_task(self.conn, task["task_id"], ["outputs/test.md"])
        with patch.dict(
            "events.bus.HANDLERS",
            {"github": lambda notification: {"status": "sent", "external_id": "github-comment-1"}},
        ):
            result = publish_pending_events(self.conn, limit=20)
        self.assertTrue(any(item["channel"] == "github" for item in result["published"]))
        github_notifications = self.conn.execute(
            "SELECT COUNT(*) AS count FROM notifications WHERE channel = 'github'"
        ).fetchone()["count"]
        self.assertGreaterEqual(github_notifications, 1)

    def test_watcher_and_health_report(self) -> None:
        watch_root = Path(self.tmpdir.name) / "watched"
        watch_root.mkdir(parents=True, exist_ok=True)
        watched_file = watch_root / "note.md"
        watched_file.write_text("# test\n", encoding="utf-8")

        first_scan = scan_local_assets(self.conn, roots=[str(watch_root)])
        second_scan = scan_local_assets(self.conn, roots=[str(watch_root)])
        self.assertEqual(first_scan["changes"][0]["diff_type"], "created")
        self.assertEqual(second_scan["changes"], [])

        report = build_health_report(self.conn)
        self.assertIn("status_counts", report)
        self.assertIn("knowledge_diffs", report)

    def test_codex_runner_completes_task_with_target_paths(self) -> None:
        task = create_task(
            self.conn,
            title="README を整備する",
            agent_id="komiya-sakura",
            payload={
                "request": "README.md を追加して quickstart をまとめる",
                "target_paths": ["README.md"],
            },
        )
        dispatch_ready_tasks(self.conn)
        with patch("control.codex_runner._git_changed_paths", side_effect=[[], ["README.md"]]), patch(
            "control.codex_runner._repo_path_exists",
            return_value=True,
        ), patch("control.codex_runner._run_codex_exec", return_value={"status": "ok", "last_message": "README.md を追加しました"}):
            result = run_codex_task(self.conn, task_id=task["task_id"], runner_id="codex")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["changed_paths"], ["README.md"])
        self.assertEqual(result["task"]["outputs"][0]["path"], "README.md")

    def test_skill_monitor_flags_degraded_skill_and_enqueues_task(self) -> None:
        self.conn.execute(
            """
            INSERT INTO skill_runs (task_id, agent_id, skill_id, result, score, created_at)
            VALUES
              ('t1', 'kirishima-ren', 'api-design-review', 'completed', 0.9, '2026-03-20T00:00:00+00:00'),
              ('t2', 'kirishima-ren', 'api-design-review', 'failed', 0.0, '2026-03-21T00:00:00+00:00'),
              ('t3', 'kirishima-ren', 'api-design-review', 'failed', 0.0, '2026-03-22T00:00:00+00:00'),
              ('t4', 'kirishima-ren', 'api-design-review', 'failed', 0.0, '2026-03-23T00:00:00+00:00')
            """
        )
        self.conn.commit()

        skills = analyze_skill_health(self.conn, recent_days=30)
        api_review = next(item for item in skills if item["skill_id"] == "api-design-review")
        self.assertTrue(api_review["flagged"])
        self.assertEqual(api_review["trend"], "broken")

        result = enqueue_improvement_tasks(self.conn, recent_days=30, dry_run=False)
        self.assertEqual(result["flagged"], 1)
        created = next(item for item in result["tasks"] if item["status"] == "created")
        task = self.conn.execute("SELECT title, source FROM tasks WHERE task_id = ?", (created["task_id"],)).fetchone()
        self.assertEqual(task["source"], "self-improve")
        self.assertIn("api-design-review", task["title"])


if __name__ == "__main__":
    unittest.main()
