---
name: agent-watch
description: >
  Opens a live monitoring view (tmux 3-pane layout) for a code agent currently working in
  /tmp/kanban-worktrees/TASK-NNN-*/. Shows git status of the worktree, a tail -F of the
  agent's tool-call log (.agent.log), and the kanban BOARD.md, all refreshed live.
  Without argument, lists currently active agents (those whose .agent.log has been written
  in the last 5 minutes) and asks which one to watch.
  Trigger on: "agent-watch", "watch agent", "watch TASK-NNN", "observe agent",
  "what is agent doing", "live view of TASK-NNN", "monitor agent", "tmux watch",
  "show me what TASK-NNN is doing", "live trace TASK-NNN".
---

# /agent-watch — Live Code-Agent Observability

You open a tmux 3-pane monitoring view for a code agent running in a kanban worktree.

The user invokes this skill in two ways:

| Form | Behavior |
|---|---|
| `/agent-watch TASK-NNN` | Watch a specific task |
| `/agent-watch` | List currently active agents and ask which to watch |

You never attach the tmux session yourself — Claude's Bash tool runs non-interactively.
You create the session **detached** with `--detach`, then tell the user the exact
attach command to run **in another terminal**.

---

## Step 1 — Resolve the target task

If the user passed an argument like `TASK-003` or just `003`:
- Normalize it to `TASK-NNN` form.
- Verify the worktree exists:
  ```bash
  ls -d /tmp/kanban-worktrees/TASK-NNN-*/ 2>/dev/null
  ```
- If not found, list available worktrees and ask the user to pick:
  ```bash
  ls -1 /tmp/kanban-worktrees/ 2>/dev/null
  ```

If no argument was passed, list **currently active** agents. An agent is active if
`<worktree>/.agent.log` was modified in the last 5 minutes:

```bash
find /tmp/kanban-worktrees -maxdepth 2 -name ".agent.log" -mmin -5 2>/dev/null \
  | xargs -I{} dirname {} | xargs -I{} basename {}
```

Display the result like this:

```
Active code agents (last activity within 5 min):

  [1] TASK-003 — Consent gate and current situation web view
        Last tool: Edit src/Api/health.cs (12s ago) | loop 2/10
  [2] TASK-005 — Mobile view — nomadic dashboard consultation
        Last tool: Bash dotnet build (3s ago) | loop 1/10

Which agent do you want to watch? (1/2/TASK-NNN)
```

If no active agent, show the BOARD's `🔵 In Progress` section instead and explain that
no agent is writing to `.agent.log` right now — the user can still watch a quiet
worktree (the skill works regardless), they just won't see live tool calls.

---

## Step 2 — Launch the monitoring session

Once a `TASK-NNN` is resolved, run the helper script in **detach** mode:

```bash
bash "$(git rev-parse --show-toplevel)/.claude/scripts/agent-watch.sh" TASK-NNN --detach
```

The script:
1. Creates a tmux session named `agent-watch-TASK-NNN` (idempotent: re-running just
   re-attaches if it already exists).
2. Builds a 3-pane layout:
   - **Top-left**: `watch -n 2` of `git status` + the 10 most recently modified files
     in the worktree (excluding `.git/` and `.agent.log` itself).
   - **Top-right**: `tail -F` of `<worktree>/.agent.log`.
   - **Bottom (full width)**: `watch -n 3` of `/tasks/BOARD.md`.
3. Pre-touches `.agent.log` if it does not exist yet, so `tail` does not bail out.
4. Sets pane titles via `pane-border-status top`.

The script returns immediately in detach mode and prints the attach command.

---

## Step 3 — Hand off to the user

After the script returns successfully, tell the user **exactly** how to attach:

```
✅ tmux session 'agent-watch-TASK-NNN' is running.

Attach it from another terminal:
    tmux attach -t agent-watch-TASK-NNN

Layout:
    ┌──────────────────────┬──────────────────────┐
    │ git status (top-L)   │ tail -F agent.log    │
    │ + recent files       │   (top-R)            │
    ├──────────────────────┴──────────────────────┤
    │ /tasks/BOARD.md (bottom, full width)         │
    └─────────────────────────────────────────────┘

Useful tmux keys:
    Ctrl-b d         detach (session keeps running in the background)
    Ctrl-b ←/→/↑/↓   move between panes
    Ctrl-b z         zoom the focused pane (toggle)
    Ctrl-b [         enter scroll mode (q to exit)

When the agent finishes, kill the session:
    tmux kill-session -t agent-watch-TASK-NNN
```

If the script fails (worktree not found, tmux not installed), surface the error verbatim
to the user — do not retry blindly.

---

## Step 4 — Optional: launch /sort-task before attaching

If `BOARD.md` looks stale (e.g. its last modification timestamp is much older than the
last `.agent.log` write), suggest running `/sort-task` once before attaching so the
bottom pane shows fresh data on first paint. Don't do this automatically — just suggest.

---

## Special Cases

| Situation | Behavior |
|---|---|
| `/tmp/kanban-worktrees/` does not exist | Tell the user no agent is running and that worktrees are created by `/launch-task auto`. |
| Worktree exists but no `.agent.log` | Still launch the session (the script pre-touches the file). The right pane will be empty until the agent emits its first tool call. |
| Multiple matching worktrees for the same TASK-NNN | Should never happen (TASK-NNN is unique), but if it does, list them and ask the user to pick. |
| User asks to "stop watching" / "kill watch" | Run `tmux kill-session -t agent-watch-TASK-NNN`. |
