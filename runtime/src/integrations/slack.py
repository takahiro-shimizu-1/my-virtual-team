from __future__ import annotations

import json
from urllib import request

from config import load_virtual_team_env


def _api_call(token: str, method: str, payload: dict) -> dict:
    req = request.Request(
        f"https://slack.com/api/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _format_message(payload: dict) -> str:
    event = payload.get("event", {})
    task = payload.get("task", {})
    agent = payload.get("agent", {})
    icons = {
        "task.completed": ":white_check_mark:",
        "task.failed": ":warning:",
        "task.timeout": ":hourglass_flowing_sand:",
        "approval.requested": ":eyes:",
    }
    icon = icons.get(event.get("event_type", ""), ":information_source:")
    department = agent.get("department_name") or agent.get("department") or ""
    name = agent.get("name") or task.get("agent_id") or ""
    title = task.get("title") or event.get("event_type", "")
    return f"{icon} *[{department} {name}]* {title}"


def send_manual_message(*, agent: str, department: str, task: str, status: str) -> dict:
    payload = {
        "event": {"event_type": f"manual.{status}"},
        "task": {"title": task},
        "agent": {"name": agent, "department_name": department},
    }
    return deliver_notification({"payload": payload})


def deliver_notification(notification: dict) -> dict:
    env = load_virtual_team_env()
    token = env.get("SLACK_BOT_TOKEN", "")
    user_id = env.get("SLACK_USER_ID", "")
    if not token or not user_id:
        return {"status": "skipped", "reason": "missing_slack_credentials"}

    channel_res = _api_call(token, "conversations.open", {"users": user_id})
    channel_id = ((channel_res.get("channel") or {}).get("id")) or ""
    if not channel_id:
        return {"status": "error", "reason": "failed_to_open_dm", "detail": channel_res}

    post_res = _api_call(
        token,
        "chat.postMessage",
        {"channel": channel_id, "text": _format_message(notification["payload"])},
    )
    if not post_res.get("ok"):
        return {"status": "error", "reason": "failed_to_post", "detail": post_res}

    return {"status": "sent", "external_id": post_res.get("ts", "")}
