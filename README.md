# RaceDash – Local Agent Swarm Orchestration

This repo now ships with a Pinchy-style orchestration layer that mirrors the "agent swarm" flow (OpenClaw orchestrator + Codex/Claude executors). Pinchy owns the business context and spawns disposable coding agents, each inside its own git worktree and tmux session.

## Architecture Highlights

1. **Context Split** – OpenClaw (Pinchy) keeps the human/business context; per-task agents only load the source tree + task prompt.
2. **Isolated worktrees** – Every task gets its own branch under `feat/<task-id>` and lives inside `../RaceDash-worktrees/<task-id>`.
3. **tmux-managed agents** – Agents run inside named tmux sessions so you can steer mid-flight with `tmux send-keys`.
4. **Task registry** – `.clawdbot/active-tasks.json` (ignored) tracks session → branch → PR state. `.clawdbot/active-tasks.example.json` is committed as a template.
5. **Daemon scripts** – `scripts/pinchy_spawn_agent.py`, `scripts/pinchy_monitor.py`, and `scripts/pinchy_cleanup.py` implement the 8-step workflow described in the article.

```
.clawdbot/
  ├── config.yaml              # live settings (copy from config.example.yaml)
  ├── active-tasks.json        # runtime state (git-ignored)
  ├── active-tasks.example.json
  └── worktrees/               # optional intra-repo scratch space
scripts/
  ├── pinchy_spawn_agent.py       # Step 2: spawn agent
  ├── pinchy_monitor.py           # Step 3–7: Ralph Loop v2 babysitter
  └── pinchy_cleanup.py           # Step 8: clean up merged worktrees
```

## Setup

1. `cp .clawdbot/config.example.yaml .clawdbot/config.yaml` and tweak:
   - `worktree_root` (defaults to `../RaceDash-worktrees`)
   - Package manager command (defaults to `pnpm install`)
   - Agent command templates (Codex + Claude shown)
   - Optional Telegram notification token/chat id
2. `python3 -m pip install pyyaml` (monitor also uses `yaml`).
3. Ensure `git worktree`, `tmux`, and (optionally) `gh` CLI are installed.
4. (Optional) Create a `prompts/` folder synced with your Obsidian vault or wherever Pinchy stores scoped prompts.

## Step-by-step Flow

> Mirrors the "Full 8-step Workflow" from the article.

1. **Scope with Pinchy** – capture the task + context into a prompt file. Pinchy can also hydrate the prompt with meeting notes or prod-only data before handing it to a coding agent.
2. **Spawn the agent**
   ```bash
   python scripts/pinchy_spawn_agent.py feat-custom-templates \
     --description "Custom templates for ACME" \
     --agent codex \
     --prompt-file prompts/feat-custom-templates.md \
     --notify
   ```
   This will:
   - `git fetch origin main`
   - `git worktree add ../RaceDash-worktrees/feat-custom-templates -b feat/feat-custom-templates origin/main`
   - `pnpm install` inside the worktree (skip with `--skip-install`)
   - Launch the agent command in `tmux new-session -s codex-feat-custom-templates ...`
   - Append a record to `.clawdbot/active-tasks.json`

   You can steer mid-task via tmux:
   ```bash
   tmux send-keys -t codex-feat-custom-templates "Stop. Focus on the API layer." Enter
   tmux send-keys -t codex-feat-custom-templates "Types are defined in src/types/template.ts" Enter
   ```
3. **Monitoring loop** – add a cron entry (every 10 minutes) so Pinchy keeps watch:
   ```cron
   */10 * * * * cd /path/to/RaceDash && ./scripts/pinchy_monitor.py --verbose >> /tmp/pinchy-monitor.log 2>&1
   ```
   The monitor
   - Verifies tmux sessions are alive
   - Uses `gh pr list --head <branch>` to discover PRs
   - Tracks CI rollups (marks `awaiting_ci`, `awaiting_review`, `done`)
   - Sends optional Telegram pings when CI is green or PR merges
4. **Agent creates PR** – your agent’s run script should `git commit`, `git push`, `gh pr create --fill`. Once the PR exists the monitor stores its number.
5. **Automated review hooks** – `pinchy_monitor.py` leaves placeholders for Codex/Gemini/Claude reviewers. Extend it by adding CLI invocations (or GitHub workflows) that drop review results into `task["checks"]`.
6. **Automated tests / CI** – CI status is surfaced through GitHub’s status check rollup. A green rollup flips the task to `awaiting_review` and (optionally) notifies you.
7. **Human review** – when you get the message “PR #<n> ready for review,” hop in, check screenshots, and merge.
8. **Merge + cleanup** – once merged, run:
   ```bash
   ./scripts/pinchy_cleanup.py            # remove all done worktrees
   # or
   ./scripts/pinchy_cleanup.py --task feat-custom-templates --force
   ```
   A daily cron works well:
   ```cron
   30 3 * * * cd /path/to/RaceDash && ./scripts/pinchy_cleanup.py --force
   ```

## Extending the Loop

- **Automatic retries** – enhance `pinchy_monitor.py` with logic that respawns agents when tmux exits without producing a PR (e.g., track `attempts` and call `pinchy_spawn_agent.py` again with richer prompts).
- **Prompt memory** – log successful prompt/agent combos inside `.clawdbot/prompt-history/` to reuse for similar features.
- **Reviewer bots** – wire Codex/Gemini/Claude CLI reviewers into your CI workflow. Have them comment directly on PRs; `pinchy_monitor.py` can poll for review states and gate notifications.
- **Notification adapters** – `notifications.enabled` currently supports Telegram. Add Slack, email, or Signal by extending `send_notification`.

## Troubleshooting

- `scripts/pinchy_spawn_agent.py --dry-run` shows the commands without executing.
- Set `--session custom-name` if you want the tmux session to differ from `agent-task`.
- `--skip-install` is handy for repos that already have vendored deps.
- If `gh` isn’t configured, monitoring still updates tmux health but PR/CI data will read as "Unknown".

That’s it—you now have a local replica of the "Minions" / agent-swarm pipeline running entirely on your machine. Customize the scripts to match your product’s review gates, but the scaffolding here covers worktree isolation, agent spawning, monitoring, and cleanup.
