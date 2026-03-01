#!/usr/bin/env python3
"""Monitor active coding agents, tmux sessions, and PR health.

Intended to be run via cron (e.g. every 10 minutes) or manually.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = SCRIPT_ROOT / ".clawdbot" / "config.yaml"
REGISTRY_PATH = SCRIPT_ROOT / ".clawdbot" / "active-tasks.json"


def load_json(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise RuntimeError("active-tasks.json must contain a list")
    return data


def save_json(path: Path, payload: List[Dict[str, Any]]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def tmux_alive(session: str) -> bool:
    result = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True)
    return result.returncode == 0


def gh_available() -> bool:
    return shutil.which("gh") is not None


def run_gh(args: List[str]) -> Optional[Dict[str, Any]]:
    if not gh_available():
        return None
    cmd = ["gh", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def lookup_pr(branch: str) -> Optional[Dict[str, Any]]:
    payload = run_gh([
        "pr",
        "list",
        "--state",
        "all",
        "--head",
        branch,
        "--json",
        "number,headRefName,statusCheckRollup,isDraft,mergeStateStatus,mergedAt,closedAt"
    ])
    if not payload:
        return None
    if not isinstance(payload, list) or not payload:
        return None
    # when multiple PRs share branch take the most recent
    payload.sort(key=lambda item: item.get("number", 0), reverse=True)
    return payload[0]


def ci_checks_passed(status_rollup: Optional[List[Dict[str, Any]]]) -> bool:
    if not status_rollup:
        return False
    for item in status_rollup:
        state = item.get("state") or item.get("status")
        if state not in {"SUCCESS", "COMPLETED"}:
            return False
    return True


def send_notification(config: Dict[str, Any], message: str) -> None:
    notif = config.get("notifications") or {}
    if not notif.get("enabled"):
        return
    token = notif.get("telegram_bot_token")
    chat_id = notif.get("telegram_chat_id")
    if not token or not chat_id:
        return
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": "true"
    }).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        urllib.request.urlopen(url, data=payload, timeout=10)
    except (urllib.error.URLError, TimeoutError):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor Pinchy agents and update registry")
    parser.add_argument("--prune-complete", action="store_true", help="Remove tasks with status done")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not REGISTRY_PATH.exists():
        print("No active tasks file found. Nothing to monitor.")
        return

    config = {}
    if CONFIG_PATH.exists():
        import yaml  # type: ignore
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle)

    tasks = load_json(REGISTRY_PATH)
    updated: List[Dict[str, Any]] = []
    summaries: List[str] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for task in tasks:
        task_id = task.get("id")
        status = task.get("status", "unknown")
        session = task.get("tmuxSession")
        branch = task.get("branch")
        note_parts = []

        alive = tmux_alive(session) if session else False
        pr_info = lookup_pr(branch) if branch else None
        pr_number = pr_info.get("number") if pr_info else None
        merged_at = pr_info.get("mergedAt") if pr_info else None
        checks = pr_info.get("statusCheckRollup") if pr_info else None
        ci_pass = ci_checks_passed(checks)

        if not alive and status == "running" and not pr_info:
            task["status"] = "stalled"
            note_parts.append("tmux session exited with no PR")
        elif pr_info and merged_at:
            task["status"] = "done"
            task["pr"] = pr_number
            task["completedAt"] = merged_at or now_iso
            note_parts.append("PR merged")
            if task.get("notifyOnComplete"):
                send_notification(
                    config,
                    f"✅ {task_id} merged (PR #{pr_number})"
                )
        elif pr_info and ci_pass and status in {"running", "awaiting_ci"}:
            task["status"] = "awaiting_review"
            task.setdefault("checks", {})["ciPassed"] = True
            note_parts.append("CI green, ready for human review")
            if task.get("notifyOnComplete"):
                send_notification(
                    config,
                    f"PR #{pr_number} ready for review ({task_id})"
                )
        elif pr_info and not ci_pass:
            task["status"] = "awaiting_ci"
            note_parts.append("Waiting on CI")
        elif alive and status == "stalled":
            task["status"] = "running"

        task.setdefault("checks", {})["tmuxAlive"] = alive
        if pr_number:
            task.setdefault("checks", {})["pr"] = pr_number
        if note_parts:
            task["note"] = " | ".join(note_parts)

        updated.append(task)
        summary = f"{task_id}: {task['status']}"
        if pr_number:
            summary += f" (PR #{pr_number})"
        if args.verbose and task.get("note"):
            summary += f" -> {task['note']}"
        summaries.append(summary)

    if args.prune_complete:
        updated = [task for task in updated if task.get("status") != "done"]

    save_json(REGISTRY_PATH, updated)
    print("\n".join(summaries) or "No active tasks")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
