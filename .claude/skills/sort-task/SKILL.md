---
name: sort-task
description: >
  Read-only kanban board generator. Scans all TASK-*.md files under /tasks/, calculates
  derived states (needs_info, blocked, ready), scores ready tasks by critical-path
  priority, and writes /tasks/BOARD.md. Pure observation: never modifies TASK files,
  never launches agents, never invokes other skills. Used as the canonical refresh
  primitive — called by PostToolUse hooks on TASK file changes, by /launch-task at the
  start of every orchestration flow, and directly by the user when they only want to
  see the current state.
  Trigger on: "show the board", "refresh the board", "refresh", "kanban", "board",
  "progress status", "task dashboard", "what's the state", "état des tâches",
  "rafraîchis le kanban", "refresh le board", "met à jour BOARD.md", "sort-task".
---

# Sort-task — Kanban Board Generator

You scan the task universe and produce a fresh `/tasks/BOARD.md`. You never mutate TASK
files, never spawn agents, never invoke other skills. Your job is pure observation.

Work silently and report compactly at the end. For orchestration (launching code agents,
status transitions, worktrees), the user must call `/launch-task` separately.

---

## Sentinel — acquire before writing `tasks/BOARD.md`

A PreToolUse hook (`tasks-folder-guard.py`) rejects every Write/Edit call
targeting `tasks/BOARD.md` unless the dedicated sentinel
`/tmp/.claude-sort-task-skill.active` is present and ≤30 min old. This
sentinel is exclusive to `/sort-task` — it codifies that `/sort-task` is
the single rendering algorithm of the kanban. Other skills (`/launch-task`,
`/pr-merge-watcher`, `/code`, `/fix`) reflect their changes by editing the
TASK card frontmatter (guarded by the separate task-pipeline sentinel),
then invoking `/sort-task` to regenerate the board from scratch.

Before writing `tasks/BOARD.md`:

```bash
touch /tmp/.claude-sort-task-skill.active
```

At the very end (success or graceful abort):

```bash
rm -f /tmp/.claude-sort-task-skill.active
```

A stale sentinel grants write access to the next agent — explicit `rm -f`
on exit is preferred. The hook treats sentinels older than 30 minutes as
expired.

> This skill **never** writes TASK cards — its self-description ("Pure
> observation: never modifies TASK files") is enforced by the absence of a
> task-pipeline sentinel touch here.

---

## Step 1 — Scan the Task Universe

Find all task files:

```bash
find /tasks -name "TASK-*.md" | sort
```

For each file found, read the YAML frontmatter to extract:
- `task_id`, `capability_id`, `capability_name`, `epic`
- `status`: `todo` | `in_progress` | `in_review` | `done` | `stalled`
- `priority`: `high` | `medium` | `low`
- `depends_on`: list of blocking task references. **Two forms accepted:**
  - **Bare form** `TASK-NNN` — references a task in the **same capability** (the
    `capability_id` of the file declaring the dependency). Default when all
    tasks of a chain live in one plan.
  - **Prefixed form** `CAP.X.Y.Z/TASK-NNN` — references a task in **another
    capability**'s plan. The prefix matches the `capability_id` frontmatter of
    the depended-upon task file. Required whenever a dependency crosses a
    capability boundary (cf. `ADR-BCM-URBA-0009` producer ownership: a consumer
    capability typically depends on producer-owned contract+stub tasks).
- `task_type`: optional routing signal read by `/code`. Values: `contract-stub`
  (route to `implement-capability` Mode B regardless of zone), `full-microservice`
  (explicit standard mode), or absent (default = standard mode). This field is
  **not** used by `/sort-task` for state classification — it is surfaced to the
  caller and consumed by `/code` at routing time. Display it in the board as a
  marker on the task row when set, so users know which agent will handle it.
- `pr_url`: GitHub PR URL (present only if `status: in_review`)
- `loop_count`: number of remediation iterations used (present if the code skill ran)
- `max_loops`: configured loop budget (present if the code skill ran)
- `stalled_reason`: multiline failure summary (present only if `status: stalled`)

Also read the **body** of the file (outside the frontmatter) to detect open questions:
- **`has_open_questions`**: `true` if the file contains an `## Open Questions` section
  with at least one unchecked item (`- [ ]`).

**Build an in-memory table** with all these fields — you will need them for the following steps.

---

## Step 2 — Calculate Derived States

### Step 2a — Resolve dependency references

For each task `T` with a non-empty `depends_on` list, resolve each entry against
the in-memory task table built in Step 1:

- **Bare entry `TASK-NNN`** → look up the task with `task_id == TASK-NNN`
  AND `capability_id == T.capability_id` (i.e. same capability as `T`).
- **Prefixed entry `CAP.X.Y.Z/TASK-NNN`** → split on the first `/`. Look up the
  task with `capability_id == CAP.X.Y.Z` AND `task_id == TASK-NNN`.

If a reference cannot be resolved (no matching task file exists — typo in the
prefix, deleted dependency, etc.), treat the dependency as **unsatisfied**
(equivalent to "not done") AND flag a warning that will be surfaced in the
Step 5 compact report:

> ⚠ TASK-NNN of CAP.X.Y declares an unresolved dependency: `<ref>`

This guard protects against silent drift — a deleted or renamed dependency
must never silently let a task appear `ready`.

### Step 2b — Classify each task's derived state

For each task with `status: todo`, calculate in this priority order:

1. **`needs_info`**: `has_open_questions` is `true` — unresolved open questions remain
   in the file, regardless of the dependency state. These tasks cannot be launched
   until the questions are clarified.
2. **`blocked`**: at least one resolved dependency does not have status `done`,
   OR at least one entry could not be resolved (Step 2a)
   _(only if the task is not already `needs_info`)_
3. **`ready`**: all resolved dependencies have status `done`, the list contains no
   unresolved entries, and no open questions remain (or `depends_on` is empty)

Tasks with `status: stalled` are treated as a **terminal blocking state** — they appear
in a dedicated ⚫ board section and require explicit user intervention via `/continue-work`
before they can be relaunched. A `stalled` task **does not** count as `done` for
dependencies — tasks that depend on it stay `blocked`.

Tasks in `in_progress`, `in_review`, and `done` keep their status as-is — open questions
detected on these tasks are flagged as warnings in the board but do not change their current status.

> **Note on `in_review`**: a task in `in_review` has an open PR awaiting merge.
> It does **not** count as `done` for dependencies — a task that depends on it stays `blocked`
> until the actual merge. It also does not block launching other tasks on the same
> capability: the code work is finished, only human validation is pending.

---

## Step 3 — Calculate Priority Score (for "ready" tasks)

For each `ready` task, calculate a **prioritization score**:

```
blocking_count  = number of tasks (directly or transitively) that depend on this task,
                  counting both bare and prefixed references — i.e. dependencies are
                  resolved across capability boundaries
priority_weight = high → 3 | medium → 2 | low → 1
score           = blocking_count × 10 + priority_weight
```

The transitive walk uses the resolved dependency graph from Step 2a: a producer-side
task that is referenced (via the prefixed form) by tasks in another capability has
those cross-cap dependents counted in its `blocking_count`.

Sort `ready` tasks by descending score → these are the candidates `/launch-task` will
prioritize first.

**Calculation examples:**
- `BNK.RLVR.CAP.BSP.001.SCO/TASK-001` → score 53 — directly blocks `BNK.RLVR.CAP.CAN.001.TAB/TASK-002`,
  which transitively blocks `TASK-003/004/005/006` of the same capability. Total
  5 tasks × 10 + high×3 = 53.
- `BNK.RLVR.CAP.CAN.001.TAB/TASK-004` → score 12 (blocks 1 task × 10 + medium×2 = 12)

---

## Step 4 — Write /tasks/BOARD.md

Write the file with this exact format. Always display the board **in the conversation**
in addition to writing the file.

```markdown
# Task Board — [DATE]

> Generated by /sort-task — refresh with `/sort-task`, launch tasks with `/launch-task`

## 🔵 In Progress

| Task | Capability | Title | Epic |
|------|-----------|-------|------|
| TASK-NNN | CAP.X.NNN | Title | Epic N |

_No tasks in progress_ (if empty)

---

## 🟡 Awaiting Merge (PR open)

| Task | Capability | Title | PR |
|------|-----------|-------|----|
| TASK-NNN | CAP.X.NNN | Title | [#42](https://github.com/org/repo/pull/42) |

_No PR awaiting merge_ (if empty)

---

## 🟢 Ready to Start (by priority)

| # | Task | Capability | Title | Priority | Score | Unblocks |
|---|------|-----------|-------|----------|-------|---------|
| 1 | TASK-001 | BNK.RLVR.CAP.CAN.001 | Freeze event contract | high | 53 | TASK-002, 003, 004 |
| 2 | TASK-007 | BNK.RLVR.CAP.BSP.001 | Other task | medium | 12 | TASK-008 |

_No ready tasks_ (if empty)

---

## 🟠 Awaiting Additional Information

> These tasks contain unresolved open questions (`- [ ]` in `## Open Questions`).
> They cannot be launched until these questions are clarified.

| Task | Capability | Title | Open Questions |
|------|-----------|-------|--------------------|
| TASK-NNN | CAP.X.NNN | Title | 2 pending question(s) |

_No tasks awaiting information_ (if empty)

---

## ⚫ Stalled (loop budget exhausted — human required)

> These tasks exceeded their remediation loop budget. No further automated work will be
> attempted. Run `/continue-work TASK-NNN` to reset the budget and relaunch.

| Task | Capability | Title | Loops used | Last failing criteria |
|------|-----------|-------|------------|----------------------|
| TASK-NNN | CAP.X.NNN | Title | 10/10 | ❌ Criterion X, ❌ Criterion Y |

_No stalled tasks_ (if empty)

---

## 🔴 Blocked

| Task | Capability | Title | Blocked By |
|------|-----------|-------|------------|
| TASK-002 | BNK.RLVR.CAP.CAN.001.TAB | Subscription point and consumption layer | BNK.RLVR.CAP.BSP.001.SCO/TASK-001, BNK.RLVR.CAP.BSP.001.PAL/TASK-001, BNK.RLVR.CAP.BSP.004.ENV/TASK-001 |
| TASK-003 | BNK.RLVR.CAP.CAN.001.TAB | Consent gate and current situation web view | TASK-002 |

_No blocked tasks_ (if empty)

> **Format**: when a blocking dependency lives in another capability, display
> the **prefixed form** `CAP.X.Y.Z/TASK-NNN` so the source plan is unambiguous.
> Same-capability dependencies stay in **bare form** `TASK-NNN`. Unresolved
> dependency references (typo, deleted task) are displayed verbatim and the
> task is treated as `blocked`; a warning is also emitted in the Step 5 report.

---

## ✅ Done

| Task | Capability | Title |
|------|-----------|-------|
| TASK-000 | CAP.X | Title |

_No completed tasks_ (if empty)

---

## Critical Path

```
TASK-001 → TASK-002 → TASK-003
                    ↘ TASK-004 (parallel)
```

**Next to launch:** TASK-001 (score 53) — [reason: unblocks 5 tasks]
```

If no TASK-*.md exists, write an empty BOARD.md containing only the message
`No tasks found in /tasks/.` and proceed to Step 5.

---

## Step 5 — Compact Report

Output a structured single-block report so `/launch-task` (or the user) can act on it
without re-reading BOARD.md:

```
📋 Board refreshed — [DATE]
Counts: ready=N, in_progress=N, in_review=N, blocked=N, needs_info=N, stalled=N, done=N
Top ready: TASK-XXX (score N), TASK-YYY (score N), TASK-ZZZ (score N)
Stalled (need /continue-work): TASK-AAA, TASK-BBB
Unresolved dependency references:
  - TASK-NNN (CAP.X.Y) → `<ref>` (no matching task)
Board: /tasks/BOARD.md
```

If a section is empty (e.g. no stalled tasks, no unresolved refs), omit the line.

---

## Boundaries

This skill is read-only. It MUST NOT:

- Modify TASK file frontmatter (status transitions belong to `/launch-task` and `/code`)
- Create branches or worktrees
- Spawn `code` sub-agents
- Invoke other skills

For any of the above, the user invokes `/launch-task` (which itself calls `/sort-task`
first to get a fresh state, then orchestrates).
