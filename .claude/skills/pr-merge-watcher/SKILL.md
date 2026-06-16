---
name: pr-merge-watcher
description: >
  Checks the status of open GitHub PRs for tasks with `status: in_review`,
  and automatically transitions tasks whose PR has been merged to `status: done`.
  Refreshes /tasks/BOARD.md and identifies newly unblocked tasks.
  Also inspects each open PR's CI/build status: when the pipeline is failing,
  harvests the essential information from the build logs and dispatches the
  `/fix` skill on that PR (idempotent — never re-triggers `/fix` on the same
  head SHA).
  Trigger on: "check PRs", "check merges", "pr-merge-watcher",
  "are there any merged PRs", "update the board after merge".
  Can also be launched via /loop for periodic local polling.
---

# PR Merge Watcher

Monitors GitHub PRs for `in_review` tasks and:

1. Closes those whose PR has been merged (status → `done`).
2. Detects open PRs whose CI pipeline is failing and dispatches `/fix` with a
   normalized failure bundle harvested from the GitHub checks.

Updates the kanban board accordingly.

---

## Sentinel — acquire before writing TASK cards

A PreToolUse hook (`tasks-folder-guard.py`) rejects every Write/Edit/MultiEdit/
NotebookEdit call targeting `tasks/<CAP>/TASK-*.md` unless the shared
task-pipeline sentinel `/tmp/.claude-task-pipeline.active` is present and
≤30 min old. This skill is on the allowlist (together with `/task`,
`/task-refinement`, `/launch-task`, `/code`, `/fix`, and `/continue-work`).
The `/fix` dispatches this skill triggers on red CI run in their own
sessions and acquire their own sentinel — `/pr-merge-watcher` only needs
the sentinel for its own status transitions (`in_review` → `done`).

Before the first TASK-card write:

```bash
touch /tmp/.claude-task-pipeline.active
```

At the very end (success or graceful abort):

```bash
rm -f /tmp/.claude-task-pipeline.active
```

If polling several PRs takes more than ~25 minutes, re-`touch` the
sentinel just before each TASK-card edit. A stale sentinel grants write
access to the next agent — explicit `rm -f` on exit is preferred.

> BOARD.md is **not** guarded by this sentinel. `/pr-merge-watcher`
> reflects its changes by editing TASK cards and then invoking
> `/sort-task`, which holds the separate `tasks/BOARD.md` sentinel.

---

## Step 1 — Find Tasks in Review

```bash
grep -rl 'status: in_review' tasks/*/TASK-*.md 2>/dev/null
```

If no files are found: terminate silently, no commit.

---

## Step 2 — Extract PR URLs

For each file found, read the YAML frontmatter and extract `pr_url:`
(expected format: `https://github.com/<PRODUCT_IMPL_REPO>/pull/NNN`, where
`<PRODUCT_IMPL_REPO>` is this implementation repo's `owner/name` slug — read
it once from `gh repo view --json nameWithOwner -q .nameWithOwner`, never hardcoded).

If a task has `status: in_review` but no `pr_url`: skip it and display a warning:
> "⚠ TASK-NNN: status in_review but no pr_url — skipped."

---

## Step 3 — Fetch PR State + CI Status

For each PR URL, extract the number (last path segment) and run **once**:

```bash
gh pr view <NNN> --repo <PRODUCT_IMPL_REPO> \
  --json number,state,mergedAt,headRefName,headRefOid,title,statusCheckRollup
```

Capture:

- `state` and `mergedAt` — used to detect a merged PR.
- `headRefOid` — the current head SHA (used for `/fix` idempotency).
- `headRefName` — branch name (passed to `/fix`).
- `statusCheckRollup` — array of check runs. Each entry exposes
  `name`, `status` (`COMPLETED`, `IN_PROGRESS`, `QUEUED`, …) and
  `conclusion` (`SUCCESS`, `FAILURE`, `TIMED_OUT`, `CANCELLED`,
  `ACTION_REQUIRED`, `NEUTRAL`, `SKIPPED`, …).

---

## Step 4 — Classify Each PR

For each task / PR pair, derive a **bucket** from the data fetched in Step 3:

| Bucket          | Condition                                                                                         |
|-----------------|---------------------------------------------------------------------------------------------------|
| `merged`        | `state == "MERGED"` or `mergedAt` non-null                                                        |
| `ci-pending`    | At least one check with `status` in {`IN_PROGRESS`, `QUEUED`, `REQUESTED`, `WAITING`, `PENDING`}  |
| `ci-failing`    | All checks `COMPLETED` AND at least one `conclusion` in {`FAILURE`, `TIMED_OUT`, `CANCELLED`, `ACTION_REQUIRED`} |
| `ci-green`      | All checks `COMPLETED` AND every `conclusion` is `SUCCESS` / `NEUTRAL` / `SKIPPED`                |
| `no-checks`     | `statusCheckRollup` is empty                                                                      |

Process buckets independently in the order below. A `merged` PR is processed
even if its last pre-merge CI was failing — merge wins.

---

## Step 5 — Close Tasks Whose PR Is Merged (`merged` bucket)

For each task in the `merged` bucket:

1. Modify the task file:
   - `status: in_review` → `status: done`
   - Keep `pr_url:` as-is (traceability).

2. Stage and commit **only** the modified files (never `git add -A`):

```bash
git config user.email "pr-watcher@claude-code"
git config user.name "Claude PR Watcher"
git add tasks/<capability>/TASK-NNN-*.md
git commit -m "chore(TASK-NNN): mark done after PR merge

PR: <pr_url>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Step 6 — Rebuild BOARD.md

Scan all task files:

```bash
find plan -name 'TASK-*.md' | sort
```

Rebuild `/tasks/BOARD.md` with the following structure:

```markdown
# Task Board — YYYY-MM-DD HH:MM UTC

> Auto-refreshed by pr-merge-watcher — manual update with `/sort-task`

## 🔵 In Progress
| Task | Capability | Title | Epic |
(tasks with status: in_progress)

## 🟡 Awaiting Merge (PR open)
| Task | Capability | Title | PR |
(tasks with status: in_review — link pr_url as [#NNN](url))

## 🟢 Ready to Start
| # | Task | Capability | Title | Priority | Unblocks |
(tasks with status: todo whose all depends_on are done)

## 🔴 Blocked
| Task | Capability | Title | Blocked By |
(tasks with status: todo with at least one non-done depends_on)

## ✅ Done
| Task | Capability | Title |
(tasks with status: done)
```

> A task in `in_review` does **not** count as `done` for dependencies.

Stage and commit BOARD.md:

```bash
git add tasks/BOARD.md
git commit -m "chore(board): refresh after PR merge watcher run"
```

---

## Step 7 — Push

```bash
git push origin main
```

If the push fails (divergence): **do not force-push**. Display the error and
stop. Suggest the user run `git pull --rebase` then re-launch.

---

## Step 8 — Dispatch `/fix` on Failing CI (`ci-failing` bucket)

This step runs **after** Steps 5–7 so that any merge transitions are committed
and pushed before `/fix` starts mutating worktrees. PRs in the `ci-pending`,
`ci-green`, or `no-checks` buckets are left alone.

### 8.1 — Idempotency guard (skip already-fixed head SHAs)

For each PR in the `ci-failing` bucket, fetch the existing watcher comments:

```bash
gh pr view <NNN> --repo <PRODUCT_IMPL_REPO> \
  --json comments --jq '.comments[] | select(.author.login=="github-actions[bot]" or (.body | startswith("pr-merge-watcher:"))) | .body'
```

If any prior watcher comment matches the marker
`pr-merge-watcher: dispatched /fix at <headRefOid>` for the **current**
`headRefOid`, skip this PR — `/fix` already ran on this exact failing commit.
The next iteration of the watcher will pick it up again only after a new
commit lands on the branch.

Also skip the PR when the corresponding TASK file has
`loop_count >= max_loops` (or `status: stalled`) — the budget is exhausted
and the user must run `/continue-work` to grant more loops. Emit:

> "⚠ TASK-NNN: PR #N is failing CI but loop budget is exhausted — run `/continue-work TASK-NNN`."

### 8.2 — Harvest the failure bundle from build logs

For each remaining `ci-failing` PR, collect the failing checks and a tight
log excerpt — these are the "essential information" passed to `/fix`:

```bash
# 1. List the failing checks for this PR.
gh pr checks <NNN> --repo <PRODUCT_IMPL_REPO> \
  --json name,state,conclusion,description,link

# 2. For every check whose conclusion is FAILURE/TIMED_OUT/CANCELLED/ACTION_REQUIRED,
#    pull the failed-step log lines from the underlying run.
RUN_ID=$(gh run list --repo <PRODUCT_IMPL_REPO> \
  --branch <headRefName> --json databaseId,conclusion,headSha \
  --jq '.[] | select(.headSha=="<headRefOid>" and (.conclusion=="failure" or .conclusion=="timed_out" or .conclusion=="cancelled")) | .databaseId' | head -1)

gh run view "$RUN_ID" --repo <PRODUCT_IMPL_REPO> --log-failed > /tmp/pr-<NNN>-failed.log
```

From the harvested data, build a **FAILURE_BUNDLE** matching the structure
`/fix` expects in its Step 0:

```
Source: pr-checks
PR: #<NNN> — <title>
Branch: <headRefName>
Head SHA: <headRefOid>

Failing checks:
  ❌ <check name>: <conclusion> — <description (single line)>
     Link: <check link>
  ❌ <...>

Raw excerpt (truncated to ~30 lines, head + tail of /tmp/pr-<NNN>-failed.log,
ANSI stripped, noise lines like "##[group]" / "##[endgroup]" dropped):
  <…relevant lines only…>
```

Trim aggressively: keep at most ~30 lines total per PR — head of the failure
(the first `error:` / `FAILED` line and its immediate context) + tail (the
final summary). Anything more is noise for `/fix`.

### 8.3 — Mark the PR (write the idempotency marker BEFORE invoking `/fix`)

Post the marker comment now so a concurrent watcher tick (e.g. when running
under `/loop 5m`) does not re-dispatch the same fix:

```bash
gh pr comment <NNN> --repo <PRODUCT_IMPL_REPO> --body "$(cat <<'BODY'
pr-merge-watcher: dispatched /fix at <headRefOid>

Failing checks:
- <check 1> (<conclusion>)
- <check 2> (<conclusion>)
BODY
)"
```

### 8.4 — Invoke `/fix`

Invoke the `/fix` skill **once per failing PR**, sequentially (never in
parallel — `/fix` mutates a worktree and pushes to a branch). Pass the PR
number plus the harvested FAILURE_BUNDLE so `/fix` can short-circuit its own
log harvesting:

```
/fix --pr <NNN>

── REMEDIATION CONTEXT (from pr-merge-watcher) ──
<FAILURE_BUNDLE built in 8.2, verbatim>
── END REMEDIATION CONTEXT ──
```

`/fix` owns its own loop-count bookkeeping, branch reuse, agent dispatch,
test re-validation, commit, push, and PR comment. The watcher does not
touch the failing branch itself.

If `/fix` returns a stall (loop budget exhausted) or a flake-suspected exit,
note it in the final report (Step 9) but do **not** retry on the same tick.

---

## Step 9 — Report

Display a summary that covers all three outcomes:

```
PR Merge Watcher — YYYY-MM-DD HH:MM

Closed tasks (merged):
  ✅ TASK-NNN: [title] (PR #NNN merged)

Newly unblocked:
  🟢 TASK-NNN: [title] (was blocked by TASK-NNN)

Still in review (CI green / pending):
  🟡 TASK-NNN: [title] — PR #NNN open, checks <green | pending>

Dispatched /fix (CI failing):
  🔧 TASK-NNN: [title] — PR #NNN, head <sha7>
     Failing: <check 1>, <check 2>
     /fix outcome: <pushed fix | stalled | suspected flake>

Skipped (already fixed at this SHA / loop budget exhausted):
  ⏭ TASK-NNN: PR #NNN @ <sha7> — <reason>
```

If nothing changed and no `/fix` was dispatched: no output, no commit.

---

## Local Polling Usage

To monitor continuously (every 5 minutes) during a work session:

```
/loop 5m /pr-merge-watcher
```

For a single manual pass:

```
/pr-merge-watcher
```

> Under `/loop`, the idempotency marker (Step 8.3) prevents the same failing
> head SHA from being fixed twice. A new `/fix` is only dispatched when a new
> commit lands on the PR branch (which changes `headRefOid`), or when the
> user resets the loop budget with `/continue-work`.
