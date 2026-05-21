---
name: launch-task
description: >
  Task orchestrator for driving the implementation of business capabilities. Always
  starts by invoking /sort-task to obtain a fresh kanban board, then orchestrates
  launches: manual selection of one ready task, fully autonomous parallel auto-launch
  (one isolated git worktree + one code sub-agent per eligible task), reactive
  auto-launch on transitions to `ready`, and status transitions (todo → in_progress →
  in_review → done). Enforces idempotency (one code agent per task) and the
  "one active task per capability" rule. Reads but never duplicates the board scan
  logic — for read-only board generation use /sort-task.
  Trigger on: "launch task", "which tasks are ready", "dequeue tasks", "dequeue",
  "auto-dequeue", "which task to launch", "which task to start", "launch next task",
  "scheduler", "start work", "what's next", "next task", "launch ready tasks",
  "launch everything autonomously", "auto", "auto mode", "execute in parallel",
  "launch autonomously".
---

# Launch-task — Task Orchestrator

You are the scheduler of the implementation pipeline. Your role: from a fresh kanban
board (always obtained by invoking `/sort-task` first), decide what to launch,
prepare isolated environments, spawn code sub-agents, and manage status transitions.

You **never** duplicate the board scan logic — that is the exclusive responsibility of
`/sort-task`. You read its output and act on it.

---

## Sentinel — acquire before writing TASK cards

A PreToolUse hook (`tasks-folder-guard.py`) rejects every Write/Edit/MultiEdit/
NotebookEdit call targeting `tasks/<CAP>/TASK-*.md` unless the shared
task-pipeline sentinel `/tmp/.claude-task-pipeline.active` is present and
≤30 min old. This skill is on the allowlist (together with `/task`,
`/task-refinement`, `/code`, `/fix`, `/continue-work`, and
`/pr-merge-watcher`). The agents this skill spawns (`code` sub-agents in
isolated worktrees) never touch TASK cards directly from this orchestrator —
each spawned `code` session acquires its own sentinel.

Before the first TASK-card write (status transitions, etc.):

```bash
touch /tmp/.claude-task-pipeline.active
```

At the very end (success or graceful abort):

```bash
rm -f /tmp/.claude-task-pipeline.active
```

If the orchestration spans more than ~25 minutes between TASK-card writes
(e.g. while waiting for `/sort-task` to complete or between two manual
launches), re-`touch` the sentinel just before the next write to refresh
its freshness window. A stale sentinel grants write access to the next
agent — explicit `rm -f` on exit is preferred.

> BOARD.md is **not** guarded by this sentinel. `/launch-task` reflects its
> changes by editing TASK cards and then invoking `/sort-task`, which holds
> the separate `tasks/BOARD.md` sentinel.

---

## Hard rule — `process/{capability-id}/` is read-only

Every worktree this skill creates under `/tmp/kanban-worktrees/TASK-NNN-*/`
inherits a copy of `process/{capability-id}/`. The `code` agents you spawn in
those worktrees, and the test agents that follow, treat that folder as a
**read-only contract**. The `process-folder-guard.py` PreToolUse hook blocks
every Write/Edit attempt under `process/**` outside the `/process` skill —
this applies in both the main checkout and the worktrees.

Concretely:

- The `code` / `fix` agents you spawn must not commit any change under
  `process/{capability-id}/` to their feature branch.
- The PRs / CI-CD pipelines opened by those agents must not contain any diff
  under `process/{capability-id}/`.
- If a `code` agent reports that the model needs to change to satisfy the
  task, treat it as a **stall** signal: stop the agent, tell the user to run
  `/process <CAPABILITY_ID>` to amend the model in a separate session, then
  reschedule the task once the model has been updated and merged.

When you create a new worktree, propagate this constraint by including in the
agent prompt:

> "process/{capability-id}/ is the read-only contract for this task. Read it
> for AGG / CMD / POL / PRJ / QRY / bus topology / JSON Schemas, but never
> modify any file under process/. The PreToolUse hook
> process-folder-guard.py will block any such attempt."

---

## Readiness gate — process model must be merged on `main`

Before launching any code agent for a task whose capability is `<CAP_ID>`,
verify that `process/<CAP_ID>/` is on `main` AND that no `process/<CAP_ID>`
PR is still open. The agent worktree is forked from `main`, so an unmerged
process model would never reach the agent — and silently launching against
an empty `process/<CAP_ID>/` produces a useless run.

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
CAP_ID="<CAPABILITY_ID-of-the-task-about-to-launch>"

# 1. Folder must exist on main.
git -C "$PROJECT_ROOT" ls-tree --name-only main -- "process/$CAP_ID" \
    > /tmp/process-main-check.txt
if [ ! -s /tmp/process-main-check.txt ]; then
  echo "GATE-FAIL: process/$CAP_ID/ is not on main."
  echo "Cannot launch tasks for $CAP_ID — run /process $CAP_ID first and merge the PR."
  # SKIP this candidate; continue with other capabilities in auto mode.
fi

# 2. No open PR for the process branch.
OPEN_COUNT=$(gh pr list --head "process/$CAP_ID" --state open --json number --jq 'length' 2>/dev/null || echo 0)
if [ "$OPEN_COUNT" != "0" ]; then
  PR_URL=$(gh pr list --head "process/$CAP_ID" --state open --json url --jq '.[0].url')
  echo "GATE-FAIL: open process PR ($PR_URL) is pending review for $CAP_ID."
  echo "Cannot launch tasks for $CAP_ID until the PR is merged."
  # SKIP this candidate; continue with other capabilities in auto mode.
fi
```

In **manual mode** (`launch TASK-NNN`), a gate failure is a hard stop —
report the gate-fail message and refuse to launch. In **auto mode**,
silently skip every candidate whose capability fails the gate (do not
launch them) and surface the skipped list in the final summary so the user
knows which capabilities still need their process PR merged.

---

## Usage Cycle

The skill supports four main intents:

| Intent | Examples |
|--------|---------|
| **Launch a task (manual)** | "launch TASK-001", "start next", "dequeue", "which task?" |
| **Automatic launch (parallel)** | "auto", "launch everything", "auto-dequeue", "launch ready tasks", "auto mode" |
| **Close a task** | "TASK-001 is done", "mark done TASK-002" |
| **Merge a PR** | "PR for TASK-001 merged", "TASK-001 accepted", "close TASK-001 after merge" |

Identify the intent, then execute the right path below. **Every path begins with Step 1.**

For pure board viewing without any orchestration, the user invokes `/sort-task` directly
(this skill is not the right entry point for that).

---

## Step 1 — Always Refresh the Board First (mandatory)

Before any decision, invoke `/sort-task` to obtain a fresh state of the kanban:

```
Skill: sort-task
```

`/sort-task` writes `/tasks/BOARD.md` and returns a compact report with:
- Counts per status (`ready`, `in_progress`, `in_review`, `blocked`, `needs_info`, `stalled`, `done`)
- Top ready tasks with their priority scores
- Stalled tasks needing `/continue-work`

Use this report as the **single source of truth** for all subsequent decisions in this
flow. Do NOT re-scan TASK files yourself.

If the report shows zero `ready` tasks AND zero `in_progress` AND zero `in_review`, the
queue is empty — explain why (everything blocked / everything done / all `needs_info`)
and stop.

---

## Step 2 — Automatic Parallel Launch (intent "auto")

If the intent is an automatic launch ("auto", "launch everything", "auto-dequeue", etc.),
execute this complete algorithm without asking the user for confirmation.

---

### Phase A — Candidate Selection

From the `/sort-task` report's `ready` list:

1. **Busy capability filter**: exclude any task whose `capability_id` already has a task
   `in_progress` or `in_review` (code work is still ongoing for that capability).
2. **Result**: list of **eligible candidates**, sorted by descending score.

(Tasks classified `needs_info` are already absent from the `ready` list — `/sort-task`
filtered them out in its derived-state computation.)

---

### Phase B — Decision Report (before launch)

Display the decision table in the conversation:

```
🤖 Automatic launch — [N] task(s) selected

| # | Task | Capability | Score | Selection Reason |
|---|------|-----------|-------|---------------------|
| 1 | TASK-001 | BNK.RLVR.CAP.CAN.001 | 53 | Critical path, unblocks 5 tasks |
| 2 | TASK-007 | BNK.RLVR.CAP.BSP.001 | 12 | Independent capability |

Excluded tasks:
- TASK-003: capability BNK.RLVR.CAP.CAN.001 already active via TASK-001
- TASK-009: 🟠 unresolved open questions — check the `## Open Questions` section of the task file

Creating isolated environments and launching agents...
```

If no eligible candidates, display the board and explain precisely why nothing can be
launched (all blocked / all done / all capabilities busy).

---

### Phase C — Isolated Environment Preparation

For **each eligible candidate**, in score order (highest first):

#### C.1 — Identify Paths

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
TASK_ID="TASK-NNN"           # e.g. TASK-003
TASK_SLUG="<title-kebab>"    # e.g. beneficiary-dashboard
BRANCH_NAME="feat/${TASK_ID}-${TASK_SLUG}"
WORKTREE_PATH="/tmp/kanban-worktrees/${TASK_ID}-${TASK_SLUG}"
```

#### C.2 — Update Status in the Task File

Before creating anything, modify the task file frontmatter:
- `status: todo` → `status: in_progress`
- Add below the frontmatter: `> **Started on:** [DATE]`

#### C.3 — Create the Branch and Worktree

```bash
# Create the branch from main without changing the current HEAD
git branch "$BRANCH_NAME" main

# Create an isolated worktree (dedicated working directory)
mkdir -p /tmp/kanban-worktrees
git worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
```

If the branch already exists (re-launch after partial failure):
```bash
git worktree add "$WORKTREE_PATH" "$BRANCH_NAME" 2>/dev/null || \
  git worktree add "$WORKTREE_PATH" --checkout "$BRANCH_NAME"
```

If the worktree already exists (same case): use it as-is without recreating.

#### C.4 — Read the Task File Content

Read the complete content of the `TASK-NNN-*.md` file to include in the sub-agent prompt.
Read the local roadmap at `/roadmap/{capability-id}/roadmap.md`.

For **all** BCM/ADR/vision context, fetch the capability pack from the `bcm-pack` CLI —
do NOT read `/bcm/`, `/func-adr/`, `/adr/`, `/strategic-vision/`, or `/product-vision/`
directly:

```bash
bcm-pack pack <CAPABILITY_ID> --compact > /tmp/pack-launch.json
```

Pass the parsed pack JSON (or just the capability ID + a note that the spawned agent will
re-fetch with `--deep` itself) to the sub-agent prompt. Selective slice usage at this
layer:

| Slice                       | Used by /launch-task itself                       |
|-----------------------------|---------------------------------------------------|
| `capability_self`           | branch slug, capability_name (for worktree path), zone |
| `capability_definition`     | included in the sub-agent prompt as context       |
| `emitted_business_events`   | included in the sub-agent prompt                  |
| `consumed_business_events`  | included in the sub-agent prompt                  |

The sub-agent will issue its own `bcm-pack` calls — possibly with `--deep` — when it
needs vision narratives or the rationale ADRs.

---

### Phase D — Launch Sub-Agents in Parallel

Spawn **one sub-agent per eligible candidate**, all in parallel (in the same message,
multiple simultaneous `Agent` calls). Each sub-agent receives the following prompt:

```
You are an autonomous implementation agent. You must implement task [TASK_ID] for
capability [CAPABILITY_NAME] ([CAPABILITY_ID]) using the `code` skill.

## Execution Context

- **Working directory**: `[WORKTREE_PATH]`  ← work ONLY in this directory
- **Git branch**: `[BRANCH_NAME]`  ← already created and checked out in the worktree
- **Project root**: `[PROJECT_ROOT]`
- **Capability zone**: `[ZONE]`  ← determines which implementation path the code skill will take

## Task File

[COMPLETE CONTENT OF FILE TASK-NNN-*.md]

## Capability Plan

[CONTENT OF PLAN.MD]

## Capability Pack (from `bcm-pack`)

[Inline the relevant slices of `bcm-pack pack [CAPABILITY_ID] --compact` —
 at minimum: `capability_self`, `capability_definition`, `emitted_business_events`,
 `consumed_business_events`, `carried_objects`. Do NOT inline the full pack —
 the spawned agent re-fetches with `--deep` if it needs vision narratives.]

## Knowledge access reminder

The spawned agent MUST source any further BCM/ADR/vision context via the
`bcm-pack` CLI, e.g. `bcm-pack pack [CAPABILITY_ID] --deep --compact`. It must
NOT read `/bcm/`, `/func-adr/`, `/adr/`, `/strategic-vision/`, `/product-vision/`,
or `/tech-vision/` directly — those paths are not authoritative in this checkout.

## Execution Instructions (WITHOUT user confirmation)

1. **Go to the worktree**: all your `bash` commands must use
   `[WORKTREE_PATH]` as the current directory.

2. **Invoke the `code` skill** with the complete context extracted from the task file.
   The `code` skill routes on `task_type` first, then on zone:
   - `task_type: contract-stub` (any zone) → spawn `implement-capability` in
     **Mode B** (JSON Schemas + minimal RabbitMQ-publishing stub, no full
     microservice scaffold) — Path C
   - `task_type` absent / `full-microservice`, non-CHANNEL zone → spawn
     `implement-capability` in **Mode A** (.NET microservice) — Path A
   - `task_type` absent / `full-microservice`, CHANNEL zone → spawn `create-bff`
     + `code-web-frontend` in parallel — Path B

   Pass to the code skill:
   - task_id, capability_id, capability_name, zone, level
   - Governing FUNC ADR(s)
   - Business events (names + trigger conditions)
   - Business objects involved
   - Required event subscriptions
   - Definition of Done
   - Instruction: skip the "Shall I proceed?" confirmation step and execute autonomously.

   The `code` skill will also invoke the matching test skill after implementation
   (`/test-business-capability` for non-CHANNEL → test-business-capability agent;
   `/test-app` for CHANNEL → test-app agent) and handle any remediation loop
   automatically — do not duplicate this step.

3. **After the code skill completes** (implementation + tests passing):
   a. Validate coherence with BCM if scripts exist:
      ```bash
      [ -f [PROJECT_ROOT]/tools/validate_repo.py ] && cd [PROJECT_ROOT] && python tools/validate_repo.py
      [ -f [PROJECT_ROOT]/tools/validate_events.py ] && cd [PROJECT_ROOT] && python tools/validate_events.py
      ```
   b. The code skill handles commit, PR creation, and `status: in_review` update.
      Verify the task file in the worktree now has `status: in_review` and `pr_url:` set.
   c. Clean up the worktree AFTER successful push:
      ```bash
      cd [PROJECT_ROOT]
      git worktree remove [WORKTREE_PATH] --force
      ```

4. **Final report**: return a structured summary:
   ```
   TASK-[NNN] — [TITLE]
   Zone: [ZONE]
   Implementation path: [implement-capability | create-bff + code-web-frontend]
   Test results: [N]/[Total] DoD criteria validated
   Status: in_review
   Branch: [BRANCH_NAME]
   PR: [PR_URL]
   Worktree cleaned: yes/no
   ```

## Absolute Rules

- NEVER ask the user for confirmation — work in complete autonomy.
- NEVER modify files outside of `[WORKTREE_PATH]` and the task file.
- If a step fails, document the error in your final report and stop cleanly
  (do not attempt to work around it).
- The worktree is your isolated environment — the git branch is already checked out there.
- NEVER launch a `code` agent if the task file already shows `status: in_progress`
  or `status: in_review` — another agent is already handling it.
```

---

### Phase E — Refresh the Board and Announce

After spawning all sub-agents:

1. **Re-invoke `/sort-task`** to refresh `/tasks/BOARD.md` with the new `in_progress` statuses.
2. **Display in the conversation**:
   ```
   🚀 [N] agent(s) launched in parallel:

   - TASK-001 → autonomous agent running | worktree: /tmp/kanban-worktrees/TASK-001-freeze-contract
   - TASK-007 → autonomous agent running | worktree: /tmp/kanban-worktrees/TASK-007-other-task

   Board updated → /tasks/BOARD.md

   Agents are working autonomously. Use /sort-task to check progress,
   or /pr-merge-watcher to check open PRs.
   ```

---

## Step 3 — Suggest and Confirm (intent "launch")

If the intent is to launch a task, present the 3 best `ready` candidates from the
`/sort-task` report (or fewer if fewer are available) and ask:

```
Tasks available to launch:

  [1] TASK-001 — Freeze consumed events contract (high, score 53)
      Capability: BNK.RLVR.CAP.CAN.001.TAB | Unblocks: TASK-002, 003, 004, 005, 006

  [2] TASK-007 — [title] (medium, score 12)
      Capability: BNK.RLVR.CAP.BSP.001 | Unblocks: TASK-008

Recommendation: TASK-001 — it is on the critical path and unblocks 5 tasks.

Which task to start? (1/2/another TASK-NNN)
```

If no task is `ready`: explain why (everything is blocked or everything is done) — refer
to the `/sort-task` report counts.

If the user has already named a specific task (`launch TASK-002`): verify in the
`/sort-task` report that it is indeed `ready`, otherwise explain the blockage.

---

## Step 4 — Launch a Task (manual)

Once the task is confirmed:

1. **Set status to `in_progress`** in the task file:
   - Modify the frontmatter: `status: todo` → `status: in_progress`
   - Note the start date in the file (add a line below the frontmatter if absent):
     ```
     > **Started on:** [DATE]
     ```

2. **Re-invoke `/sort-task`** to refresh `/tasks/BOARD.md` with the new status.

3. **Announce clearly**:
   ```
   Launching TASK-[NNN] — [title]
   Capability: [CAP.ID] | Epic: [Epic N]
   Board updated → /tasks/BOARD.md

   Invoking code skill...
   ```

4. **Invoke the `code` skill** passing the task context. The `code` skill reads
   the task file, prepares the summary, waits for confirmation, and delegates to
   `implement-capability`.

---

## Step 5 — Close a Task

### 5a — Transition to `in_review` (PR opened)

This status is set automatically by the `code` skill at the end of its execution.
If the user signals it manually ("TASK-NNN is in review", "PR opened for TASK-NNN"):

1. **Set status to `in_review`** in the task file.
2. **Add `pr_url:`** in the frontmatter if the user provides the URL.
3. **Re-invoke `/sort-task`** — the task moves to the 🟡 column.
4. **Announce**:
   ```
   🟡 TASK-[NNN] awaiting merge.
   PR: [URL if available]

   ⚠ Tasks depending on it remain blocked until the merge.
   ```

### 5b — PR Merge (`in_review` → `done`)

When the user signals that the PR has been merged ("PR for TASK-NNN merged",
"TASK-NNN accepted", "merge TASK-NNN"):

1. **Set status to `done`** in the task file.
2. **Remove or clear the `pr_url:` field** (optional — keeping it for traceability is acceptable).
3. **Re-invoke `/sort-task`** — the report will list newly-ready tasks (those whose
   `depends_on` are now all `done`).
4. **Trigger Step 6 — Reactive Auto-Launch** for each newly-ready task.
5. **Report**:
   ```
   ✅ TASK-[NNN] done (PR merged).

   Newly ready → auto-launching:
   - TASK-[NNN+1]: [title] → code agent spawned
   - TASK-[NNN+2]: [title] → code agent spawned (parallel)

   Board updated → /tasks/BOARD.md
   ```

### 5c — Direct Closure Without PR

If the user marks a task `done` without going through `in_review` (task without code,
design decision, etc.), directly apply the `in_progress → done` path, then
**trigger Step 6 — Reactive Auto-Launch** for each task that just became `ready`.

---

## Step 6 — Reactive Auto-Launch on `ready` Transition

This step is triggered automatically whenever one or more tasks transition to `ready`
— which happens after any task is marked `done` (Steps 5b and 5c). It can also be
invoked explicitly when the board is refreshed and `ready` tasks are found with no
active agent.

**Objective**: for each task that just became `ready`, spawn exactly one `code`
sub-agent. Never spawn more than one agent per task.

---

### 6.1 — Idempotency Check (mandatory before any launch)

For each candidate task (just became `ready`):

```
IF task.status == "in_progress"  → SKIP  (agent already running)
IF task.status == "in_review"    → SKIP  (code work done, awaiting merge)
IF task.status == "done"         → SKIP  (finished)
IF task.status == "stalled"      → SKIP  (loop budget exhausted — needs /continue-work)
IF task.status != "ready"        → SKIP  (not eligible)
IF capability already has a task with status "in_progress" → SKIP
   (same capability rule — one active task per capability at a time)
```

Only tasks that pass all checks proceed to launch.

---

### 6.2 — Mark `in_progress` Immediately (before spawning)

For each task that passed the idempotency check:

1. **Set `status: in_progress`** in the task file frontmatter **before** spawning the agent.
   This is the idempotency lock — any concurrent evaluation of the same task will see
   `in_progress` and skip it.
2. Add below the frontmatter: `> **Started on:** [DATE]`
3. **Re-invoke `/sort-task`** to refresh `/tasks/BOARD.md` with the new status.

---

### 6.3 — Spawn One `code` Agent Per Ready Task

Spawn **one sub-agent per task** that passed 6.1, all in parallel (multiple simultaneous
`Agent` calls in the same message). Use the same sub-agent prompt as Phase D (Step 2),
with the following adjustments:

- Pre-populate `[WORKTREE_PATH]` and `[BRANCH_NAME]` from the task ID and slug.
- Include the worktree creation commands (Phase C.3) **inside** the agent prompt since
  this is not "auto" mode here — the agent must set up its own environment:

  ```
  ## Worktree Setup (execute first)

  ```bash
  PROJECT_ROOT=$(git rev-parse --show-toplevel)
  BRANCH_NAME="feat/[TASK_ID]-[TASK_SLUG]"
  WORKTREE_PATH="/tmp/kanban-worktrees/[TASK_ID]-[TASK_SLUG]"
  git branch "$BRANCH_NAME" main 2>/dev/null || true
  mkdir -p /tmp/kanban-worktrees
  git worktree add "$WORKTREE_PATH" "$BRANCH_NAME" 2>/dev/null || true
  cd "$WORKTREE_PATH"
  ```
  ```

- All other instructions are identical to Phase D: invoke `code` skill, zone-aware routing,
  validation, PR creation, worktree cleanup.

---

### 6.4 — Announce

After spawning:

```
🚀 Reactive launch — [N] agent(s) auto-started:

- TASK-[NNN+1] ([CAP.ID]) → code agent spawned | worktree: /tmp/kanban-worktrees/TASK-[NNN+1]-[slug]
- TASK-[NNN+2] ([CAP.ID]) → code agent spawned | worktree: /tmp/kanban-worktrees/TASK-[NNN+2]-[slug]

Skipped (already active):
- TASK-[NNN+3]: in_progress — agent already running
- TASK-[NNN+4]: capability CAP.X.NNN already busy (TASK-NNN+5 in_progress)

Board updated → /tasks/BOARD.md
```

If no task passes the idempotency check, simply report:
```
No new task to auto-launch — all ready tasks already have an active agent.
```

---

## Scheduler Rules

**Maximum priority** — a task `in_progress` must be completed before launching a new one
on the same capability. Tasks from different capabilities can run in parallel.

**`in_review` frees the capability** — a task in `in_review` has completed its code work.
It does not block launching another task on the same capability. However, it
**does not count as `done`** for dependencies: tasks blocked by it remain
blocked until the actual merge.

**Stalled tasks are immovable** — a `stalled` task cannot be auto-launched and does not
count as `done` for dependencies. It must be explicitly resumed via `/continue-work`.
The board (generated by `/sort-task`) shows it in the ⚫ section with its loop count
and last failing criteria.

**One agent per task (strict)** — a `code` agent is spawned for a task only once.
Before any launch (reactive or manual), verify `status != in_progress` AND
`status != in_review`. Setting `status: in_progress` immediately (before spawning) is the
idempotency lock that prevents duplicate agents in concurrent or re-triggered scenarios.

**Avoid re-launches** — if a task is already `in_progress` or `in_review`, do not re-launch it.
For `in_review`, remind that the PR must be merged before it can be closed.

**Dependency integrity** — refuse to launch a `blocked` task. Clearly explain
which task must be `done` (not just `in_review`) to unblock it.

**Board always up to date** — every status change must immediately be reflected in
`/tasks/BOARD.md` by re-invoking `/sort-task`. Never leave the board stale.

**Auto mode = worktrees + sub-agents** — in automatic mode, each task gets its own
working directory (`git worktree`) and its own autonomous agent. Never checkout on
`main` or cause interference between parallel tasks. The sub-agent cleans up its worktree
after push.

**Total isolation in auto mode** — sub-agents share no state. Each agent reads
its source files from its worktree, pushes to its own branch, and opens its own PR.
This skill maintains the list of active worktrees to monitor or clean them up.

---

## Special Cases

| Situation | Behavior |
|-----------|-------------|
| No `ready` task, no `in_progress` | Everything is blocked or done — show counts from the `/sort-task` report and explain |
| All tasks `done` | Congratulate, list completed tasks (from the report), suggest moving to the next capability |
| Task `in_progress` for a long time | Mention it from the report, ask if it is done before proposing others on the same capability |
| Task `in_review` for a long time | Remind the PR URL and invite to merge or request a re-run if corrections are needed |
| `in_review` task on which blocked tasks depend | Highlight: "⚠ Merging TASK-NNN will unblock TASK-X, TASK-Y" |
| Multiple capabilities with `ready` tasks | Prioritize globally by score — capabilities are not isolated |
| Task with unresolved `Open Questions` | Already classified `needs_info` (🟠) by `/sort-task`. In manual mode: blocks launch, list unchecked questions and ask the user to resolve them. In auto mode: excluded and mentioned in the exclusion list with the 🟠 symbol. |
| Orphan worktrees (`/tmp/kanban-worktrees/`) | If a worktree exists for an `in_progress` task without an active agent, flag it: "Orphan worktree detected for TASK-NNN — re-launch the agent or clean up?" |
| `stalled` task blocking the critical path | Highlight: "⚫ TASK-NNN stalled — [N] tasks are blocked waiting for it. Run `/continue-work TASK-NNN` to unblock [N] tasks." |
| `/continue-work` received | Read `stalled_reason` + new `max_loops`, reset counters, set `status: todo`, trigger Step 6 reactive launch for the task. |
| Auto launch with no ready tasks | Show the full report, explain each blockage, suggest merging `in_review` PRs to unblock the queue |
