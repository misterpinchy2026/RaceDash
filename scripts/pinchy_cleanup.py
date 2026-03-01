#!/usr/bin/env python3
"""Remove finished agent worktrees and tidy up registry entries."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = SCRIPT_ROOT / ".clawdbot" / "active-tasks.json"


def load_tasks() -> List[Dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        return []
    with REGISTRY_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, list) else []


def save_tasks(tasks: List[Dict[str, Any]]) -> None:
    REGISTRY_PATH.write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")


def git_worktree_remove(path: Path, force: bool) -> None:
    if not path.exists():
        return
    cmd = ["git", "worktree", "remove"]
    if force:
        cmd.append("-f")
    cmd.append(str(path))
    subprocess.run(cmd, cwd=str(SCRIPT_ROOT), check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up Pinchy worktrees")
    parser.add_argument("--task", help="Only remove a specific task id")
    parser.add_argument("--force", action="store_true", help="Force-remove dirty worktrees")
    args = parser.parse_args()

    tasks = load_tasks()
    remaining: List[Dict[str, Any]] = []

    for task in tasks:
        task_id = task.get("id")
        if args.task and task_id != args.task:
            remaining.append(task)
            continue
        if task.get("status") not in {"done", "abandoned"}:
            remaining.append(task)
            continue
        worktree = task.get("worktree")
        if worktree:
            git_worktree_remove(Path(worktree), args.force)
        print(f"Removed worktree for {task_id}")

    if args.task:
        remaining = [task for task in remaining if task.get("id") != args.task]
    else:
        remaining = [task for task in remaining if task.get("status") not in {"done", "abandoned"}]

    save_tasks(remaining)


if __name__ == "__main__":
    main()
