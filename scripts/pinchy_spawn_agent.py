#!/usr/bin/env python3
"""Spawn a dedicated coding agent with its own git worktree and tmux session.

Usage example:
  python scripts/pinchy_spawn_agent.py feat-custom-templates \
    --description "Custom email templates for ACME" \
    --agent codex \
    --prompt-file prompts/feat-custom-templates.md
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

try:
    import yaml  # type: ignore
except ImportError as exc:
    print("PyYAML is required. pip install pyyaml", file=sys.stderr)
    raise

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = SCRIPT_ROOT / ".clawdbot" / "config.yaml"
REGISTRY_PATH = SCRIPT_ROOT / ".clawdbot" / "active-tasks.json"


def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        path = CONFIG_PATH
    else:
        example = SCRIPT_ROOT / ".clawdbot" / "config.example.yaml"
        if not example.exists():
            raise FileNotFoundError("No .clawdbot/config.yaml or config.example.yaml found")
        path = example
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def resolve_path(base: Path, value: str) -> Path:
    raw = Path(os.path.expanduser(value))
    return raw if raw.is_absolute() else (base / raw).resolve()


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def ensure_registry() -> list[Dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_PATH.write_text("[]\n", encoding="utf-8")
    with REGISTRY_PATH.open("r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError:
            raise RuntimeError("active-tasks.json is not valid JSON")
    if not isinstance(data, list):
        raise RuntimeError("active-tasks.json must contain a list")
    return data


def save_registry(tasks: list[Dict[str, Any]]) -> None:
    REGISTRY_PATH.write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")


def build_agent_command(template: str, prompt: str, model: str, effort: str) -> str:
    escaped_prompt = prompt.replace("\"", r"\\\"")
    cmd = template.replace("{prompt}", escaped_prompt)
    cmd = cmd.replace("{model}", model)
    cmd = cmd.replace("{effort}", effort)
    return cmd.strip()


def tmux_session_exists(name: str) -> bool:
    result = subprocess.run(["tmux", "has-session", "-t", name], capture_output=True)
    return result.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Spawn a background coding agent")
    parser.add_argument("task_id", help="Short slug, e.g. feat-custom-templates")
    parser.add_argument("--description", required=True, help="Human readable summary")
    parser.add_argument("--agent", choices=["codex", "claude"], default="codex")
    parser.add_argument("--prompt", help="Prompt string to feed the agent")
    parser.add_argument("--prompt-file", help="Path to a file containing the full prompt")
    parser.add_argument("--branch", help="Git branch name (defaults to feat/<task_id>)")
    parser.add_argument("--model", help="Override model for the agent")
    parser.add_argument("--effort", help="Override reasoning effort (e.g. high)")
    parser.add_argument("--session", help="Optional tmux session name override")
    parser.add_argument("--notify", action="store_true", help="Mark task for completion notification")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without executing")
    parser.add_argument("--skip-install", action="store_true", help="Skip package manager install step")
    args = parser.parse_args()

    if not args.prompt and not args.prompt_file:
        parser.error("Either --prompt or --prompt-file must be provided")

    prompt_text = args.prompt
    if args.prompt_file:
        prompt_path = Path(args.prompt_file)
        if not prompt_path.is_file():
            parser.error(f"Prompt file not found: {prompt_path}")
        prompt_text = prompt_path.read_text(encoding="utf-8")
    assert prompt_text is not None

    config = load_config()
    repo_root = resolve_path(SCRIPT_ROOT, config.get("repo_root", "."))
    worktree_root = resolve_path(SCRIPT_ROOT, config.get("worktree_root", "../worktrees"))
    worktree_root.mkdir(parents=True, exist_ok=True)

    base_branch = config.get("base_branch", "main")
    remote = config.get("remote", "origin")
    branch_name = args.branch or f"feat/{args.task_id}"
    worktree_path = worktree_root / args.task_id

    agent_defaults = config.get("agent_defaults", {})
    defaults = agent_defaults.get(args.agent, {})
    model = args.model or defaults.get("model") or "gpt-5.3-codex"
    effort = args.effort or defaults.get("effort") or "medium"

    agent_template = config.get("agent_commands", {}).get(args.agent)
    if not agent_template:
        parser.error(f"No agent template defined for '{args.agent}' in config")

    session_name = args.session or f"{args.agent}-{args.task_id}"
    if tmux_session_exists(session_name):
        parser.error(f"tmux session '{session_name}' already exists")

    registry = ensure_registry()
    if any(task.get("id") == args.task_id for task in registry):
        parser.error(f"Task id '{args.task_id}' already exists in registry")

    git_fetch_cmd = ["git", "fetch", remote, base_branch]
    worktree_cmd = ["git", "worktree", "add", str(worktree_path), "-b", branch_name, f"{remote}/{base_branch}"]

    install_command = None
    pkg_cmd = config.get("install_command")
    if pkg_cmd and not args.skip_install:
        install_command = pkg_cmd

    agent_command = build_agent_command(agent_template, prompt_text, model, effort)
    tmux_cmd = [
        "tmux",
        "new-session",
        "-d",
        "-s",
        session_name,
        "-c",
        str(worktree_path),
        agent_command,
    ]

    print(f"Repo root: {repo_root}")
    print(f"Worktree: {worktree_path}")
    if args.dry_run:
        print("--dry-run enabled. Commands that would run:")
        print(" ".join(git_fetch_cmd))
        print(" ".join(worktree_cmd))
        if install_command:
            print(f"(in worktree) {install_command}")
        print(" ".join(tmux_cmd))
        return

    run(git_fetch_cmd, cwd=repo_root)
    if worktree_path.exists():
        parser.error(f"Worktree path already exists: {worktree_path}")
    run(worktree_cmd, cwd=repo_root)

    if install_command:
        subprocess.run(install_command, shell=True, cwd=str(worktree_path), check=True)

    run(tmux_cmd)

    now = datetime.now(timezone.utc).isoformat()
    task_entry = {
        "id": args.task_id,
        "description": args.description,
        "agent": args.agent,
        "branch": branch_name,
        "worktree": str(worktree_path),
        "tmuxSession": session_name,
        "status": "running",
        "startedAt": now,
        "notifyOnComplete": args.notify,
        "model": model,
        "effort": effort,
    }
    registry.append(task_entry)
    save_registry(registry)
    print(f"Spawned {args.agent} agent in tmux session '{session_name}'")


if __name__ == "__main__":
    main()
