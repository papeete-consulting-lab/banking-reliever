---
name: fix
description: >
  Remediates a previously implemented task whose PR is failing CI/CD, whose post-merge
  build broke, or whose tests have regressed. Accepts the failure context as input —
  CI/CD logs, a PR number, a branch name, a TASK-NNN, a test report, or a free-form
  paste — resolves the target branch and TASK file, then routes to the same agents as
  `/code` (zone-aware: implement-capability for non-CHANNEL, create-bff +
  code-web-frontend for CHANNEL, implement-capability Mode B for contract-stub).
  Re-uses the existing PR branch (and any pre-existing worktree under
  /tmp/kanban-worktrees/) — never creates a new branch — and re-invokes the matching
  test skill (test-business-capability for non-CHANNEL, test-app for CHANNEL) to
  validate the fix in the same kind of ephemeral environment as the original test run.
  Pushes the fix to the same branch so the open PR is updated in place. Trigger on:
  "/fix", "fix this PR", "fix PR #N", "fix the failing build", "fix CI logs",
  "remediate PR #N", "the merge is failing", "fix TASK-NNN", "the build is red",
  "tests regressed", or any time a CI/CD failure or post-merge breakage needs to be
  investigated and corrected on an existing branch.
---

# Fix Skill

You are the remediation counterpart of `/code`. Your job: take a failure signal —
typically CI/CD logs from a failing PR or a regressed merge — resolve the target
branch and TASK, route to the same implementation agents as `/code`, then re-validate
with the matching test skill. You **never create a new branch** and **never open a new
PR** — you push to the existing branch so its open PR updates in place.

> **Note:** For an unfinished task that has not yet produced a PR, use `/code` (or
> `/continue-work` if it stalled). `/fix` is for tasks that **already** have an open
> branch / PR / merge whose validation is failing.

---

## Sentinel — acquire before writing TASK cards

A PreToolUse hook (`tasks-folder-guard.py`) rejects every Write/Edit/MultiEdit/
NotebookEdit call targeting `tasks/<CAP>/TASK-*.md` unless the shared
task-pipeline sentinel `/tmp/.claude-task-pipeline.active` is present and
≤30 min old. This skill is on the allowlist (together with `/task`,
`/task-refinement`, `/launch-task`, `/code`, `/continue-work`, and
`/pr-merge-watcher`). The implementation agents this skill spawns never
touch TASK cards directly — they return verdicts that this skill applies
(loop_count, pr_url, fix_pr_urls, stalled_reason, status transitions).

Before the first TASK-card write:

```bash
touch /tmp/.claude-task-pipeline.active
```

At the very end (success or graceful abort):

```bash
rm -f /tmp/.claude-task-pipeline.active
```

A `/fix` session typically spans more than 30 minutes — re-`touch` the
sentinel just before each TASK-card edit (after the remediation agent
returns, after the test skill completes, and before the final status
transition). A stale sentinel grants write access to the next agent —
explicit `rm -f` on exit is preferred.

> BOARD.md is **not** guarded by this sentinel. `/fix` reflects its
> changes by editing the TASK card and then invoking `/sort-task`, which
> holds the separate `tasks/BOARD.md` sentinel.

---

## Process model — consumed read-only via `kpack process`

> The DDD process model (aggregates, commands, policies, read-models, bus
> topology, JSON Schemas) is authored by the `/process` skill in the
> **reliever-knowledge** repo and consumed here **read-only** via
> `kpack process <CAP_ID>` — exactly like the BCM corpus via `kpack pack`.
> It does not live in this repo, so there is nothing to guard locally and
> nothing to write under `process/`.

A fix never reshapes the process model — it is the contract; the fix lives in
the implementation that must satisfy it. The model is fetched via
`kpack process <CAP_ID>`.

If the failure analysis reveals that the contract itself is wrong (an
aggregate invariant is too strict, a command schema misses a field, a routing
key is mis-paired), **stop the fix loop**. Tell the user to:

1. run `/process <CAPABILITY_ID>` in the reliever-knowledge repo to amend the model,
2. merge that change upstream,
3. re-run `/fix` against the failing PR with the refreshed model in place.

---

## Readiness gate — the process model must resolve via `kpack process`

Before re-spawning any implementation agent, verify the capability's process
model resolves. A fix must never run against an unresolvable model. A model is
ready iff `kpack process <CAP_ID>` returns exit 0 (kpack resolves the
published `main` of reliever-knowledge by default).

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
CAP_ID="<CAPABILITY_ID-of-the-failing-task>"

# The process model lives in reliever-knowledge now; it is ready iff kpack
# can resolve it (kpack resolves the published main by default).
if ! kpack process "$CAP_ID" --compact >/tmp/process-model.json 2>/tmp/process-model.err; then
  echo "GATE-FAIL: no process model for $CAP_ID."
  echo "Run /process $CAP_ID in the reliever-knowledge repo and merge its PR, then retry."
  cat /tmp/process-model.err
  exit 1
fi
```

If the gate fails, **stop and surface the failure** — the fix cannot land
without a resolvable contract.

---

## Step 0 — Resolve the Input

The user gives you a failure signal. Identify which form it takes:

| Input form | Example | What to extract |
|------------|---------|------------------|
| PR number  | `/fix PR#3`, `/fix #3`, `/fix --pr 3`         | branch via `gh pr view <N> --json headRefName,number,title` |
| Branch     | `/fix --branch feat/TASK-001-...`             | branch directly; derive PR via `gh pr list --head <branch>` |
| Task ID    | `/fix TASK-001`                               | look up `pr_url` in the TASK frontmatter; if absent, ask which branch |
| Log paste  | `/fix` followed by pasted CI/CD logs          | parse failing-test names + asserted criteria; ask for PR/branch if not deducible |
| Log file   | `/fix --log /path/to/build.log`               | read file; same parsing as paste |
| Free form  | "the merge from PR #3 broke main" | extract PR number / branch from the sentence; confirm with user before acting |

Always end Step 0 with three resolved values:

1. **`BRANCH_NAME`** — the existing feature branch (e.g. `feat/TASK-001-bsp-env-envelope-consumed`).
   - Derive the **task slug** as the suffix after `feat/TASK-NNN-`.
2. **`TASK_FILE`** — the absolute path to `tasks/{capability-id}/TASK-NNN-*.md`
   that owns this branch (TASK-NNN is encoded in the branch name).
3. **`FAILURE_BUNDLE`** — the failure context normalized into the structure below
   (used verbatim later in the REMEDIATION CONTEXT block):

   ```
   Source: [pr-checks | post-merge-ci | manual-paste | test-report]
   PR (if any): #N — <title>
   Failing items:
     ❌ [name / criterion]: <symptom — single line>
        Suggested correction (if extractable from logs): <line>
     ❌ [...]
   Raw excerpt (truncated to ~30 lines, head + tail of the failure):
     <…relevant lines only — strip ANSI, drop noise…>
   ```

   When the input is a PR number, also call:
   ```bash
   gh pr checks <N> --json name,state,description,link
   gh run view <run-id> --log-failed   # if a failing run is named in the checks
   ```
   …to harvest the actual error lines instead of asking the user to paste.

If `BRANCH_NAME` cannot be resolved, stop and ask the user which branch to apply the
fix on. Never guess.

---

## Step 1 — Read the TASK + Verify Eligibility

1. Read `TASK_FILE`. Extract: `task_id`, `capability_id`, `capability_name`,
   `task_type`, `status`, `pr_url`, `loop_count`, `max_loops`.

2. Verify eligibility:
   - **`status` must be one of** `in_review`, `done`, or `in_progress`. Anything else
     means there is nothing to fix yet — redirect to `/code` or `/continue-work`.
   - **`status: stalled`** → stop and tell the user to run
     `/continue-work TASK-NNN` first; that flow already covers stalled remediation.

3. Read loop counters. `/fix` consumes the same `loop_count` / `max_loops` budget as
   `/code` — failed CI fixes are remediation iterations on the same task. If
   `loop_count` is missing, initialize to `0` / `10`. If `loop_count >= max_loops`,
   trigger the **Stall Procedure** (Step 4 below) immediately without spawning any
   agent.

4. Fetch the capability pack — same pattern as `/code`:

   ```bash
   kpack pack <capability_id> --compact > /tmp/pack-fix.json
   ```

   `<capability_id>` is the full source-context-prefixed ID (e.g.
   `BNK.RLVR.CAP.BSP.001.SCO`); the v2.0.0 CLI rejects the short form (exit 2).
   Read `slices.capability_self[0].zoning` for routing. Never read `/bcm/`,
   `/func-adr/`, `/adr/`, `/strategic-vision/`, `/domain-vision/`, or
   `/tech-vision/` directly.

   **Check for knowledge drift first.** A failure can stem from upstream
   knowledge having moved since the artifact was built. Compare the TASK's
   `bcm_ref` against the current knowledge base:

   ```bash
   kpack diff "$bcm_ref" --capability <capability_id> --compact \
     | jq '{empty, summary}'
   ```

   If the diff is **non-empty**, the root cause may be upstream, not in the code:
   the process model is stale. Surface this in the remediation context and
   recommend re-running `/process` (→ `/roadmap` → `/task`) rather than patching
   the implementation against an outdated contract. If the diff is empty, proceed
   with the code-level remediation below.

5. Determine the **routing path** using the exact same matrix as `/code`:

   | Signal                                               | Path |
   |------------------------------------------------------|------|
   | `task_type: contract-stub` (any zone)                | **C** — `implement-capability` Mode B |
   | non-CHANNEL zone, `task_type` absent / `full-microservice` | **A** — `implement-capability` Mode A |
   | `CHANNEL`, `task_type` absent / `full-microservice`  | **B** — `create-bff` + `code-web-frontend` (parallel) |

---

## Step 2 — Reuse the Existing Branch / Worktree

`/fix` **never creates a new branch.** It reuses the branch that already exists for
this PR, and any worktree previously created by `/launch-task auto`.

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
TASK_SLUG="${BRANCH_NAME#feat/TASK-*-}"          # e.g. bsp-env-envelope-consumed
WORKTREE_PATH="/tmp/kanban-worktrees/${TASK_ID}-${TASK_SLUG}"

# Make sure the local branch reference is up to date with remote
git fetch origin "$BRANCH_NAME" --quiet || true

# Reuse the existing worktree if present, otherwise re-create it on the SAME branch
if [ -d "$WORKTREE_PATH" ]; then
  cd "$WORKTREE_PATH"
  git pull --ff-only origin "$BRANCH_NAME" 2>/dev/null || true
else
  mkdir -p /tmp/kanban-worktrees
  git worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
  cd "$WORKTREE_PATH"
fi
```

Do **not** branch off this branch. Do **not** rebase or rewrite history without an
explicit user instruction. The worktree is your editing surface; the branch's HEAD
is the base for the fix commit.

---

## Step 3 — Summarize and Invoke the Implementation Agent with Remediation Context

### 3.1 — Summarize what will be fixed

Show the user a tight pre-flight summary (skip the "Shall I proceed?" prompt when
invoked from `/launch-task auto` or another automated context):

```
Fixing TASK-[NNN] — [Title]

Capability: [Name] ([ID]) — [Zone]
Branch:     feat/TASK-NNN-{slug}      (re-using existing branch — no new branch)
Worktree:   /tmp/kanban-worktrees/TASK-NNN-{slug}
PR:         #N (state: OPEN | CLOSED | MERGED)
Loop:       [loop_count+1]/[max_loops]

Failing items detected:
  ❌ [item 1]: [symptom]
  ❌ [item 2]: [symptom]

Implementation path: [Path A: implement-capability | Path B: create-bff + code-web-frontend | Path C: implement-capability Mode B]

Shall I proceed?
```

### 3.2 — Increment loop_count and spawn the agent(s)

Before spawning, increment the task file's `loop_count` by 1 and write it back.

Spawn the same agent(s) `/code` would, but **prepend** a remediation block to the
prompt that is built directly from `FAILURE_BUNDLE`:

```
── REMEDIATION CONTEXT (loop [loop_count]/[max_loops]) ──
Source signal: [pr-checks | post-merge-ci | manual-paste | test-report]
PR: #N (branch feat/TASK-NNN-{slug})

Failing items:
  ❌ [item 1]: [symptom]
     Suggested correction: [if extractable]
  ❌ [item 2]: [symptom]
     Suggested correction: [if extractable]

Raw excerpt (truncated):
[~30 lines, head + tail]

Re-implement only what is needed to fix these items. Do not touch passing code,
do not refactor, do not introduce abstractions. The branch is already at HEAD —
add commits on top, do NOT rebase or rewrite history.
── END REMEDIATION CONTEXT ──
```

Then attach the standard task context (task file content, capability pack
slices) — same shape as `/code`, same agent type per path:

| Path | Agent(s) to spawn (same as `/code`)                          |
|------|----------------------------------------------------------------|
| A    | `implement-capability` (Mode A)                               |
| B    | `create-bff` + `code-web-frontend` (parallel, single message) |
| C    | `implement-capability` (Mode B — contract-stub)               |

If only one of the two CHANNEL components is implicated by the failure (e.g. only
the BFF's `/health` is red), spawn only that one agent — the cheapest fix for the
named failure. If the failure is ambiguous on Path B, default to spawning both.

The agents already know how to read the worktree path from their working directory
— pass `WORKTREE_PATH` in the prompt as the working directory and instruct them
NOT to create a new branch.

---

## Step 3.5 — Refresh the contract harness (Path A only)

> **Skip for Path B (CHANNEL).** The BFF owns its own contract surface via
> `create-bff`.
>
> **Skip for Path C (contract-stub).** Mode B's scaffold is too narrow for
> the full OpenAPI/AsyncAPI harness; only JSON schemas + the worker stub
> are produced.

A code change on Path A almost always shifts the public contract surface
(controller routes, action signatures, bus consumers, message contracts). If
we re-validate without re-running the harness, the committed
`contracts/specs/openapi.yaml` and `contracts/specs/asyncapi.yaml` drift
silently, and the harness's MSBuild target will fail the next `dotnet build`
on the developer's workstation. So `/fix` mirrors `/code` Step 2.5: invoke
`/harness-backend` after `implement-capability` succeeds, before the test
step.

```
Skill: harness-backend
Args:  CAPABILITY_ID = <from task>
       --branch      = <BRANCH_NAME>      # so it resolves artifacts from WORKTREE_PATH
```

Say:
> "Refreshing contract harness for TASK-[NNN] on branch `<BRANCH_NAME>` (loop [loop_count]/[max_loops])..."

The harness will regenerate `contracts/specs/openapi.yaml` +
`asyncapi.yaml` + `lineage.json` + `harness-report.md` strictly from
`process/{cap}/` + `kpack`, with full bidirectional `x-lineage` (process
+ bcm) on every operation, message, and channel. Treat its outcome the same
way `/code` Step 2.5 does:

| Harness verdict                                    | Action in `/fix`                                                              |
|----------------------------------------------------|-------------------------------------------------------------------------------|
| ✅ Closure green, drift = 0                         | proceed to Step 4 (re-validate with the test skill).                          |
| ❌ Drift > 0 (specs regenerated)                    | the new specs ARE the fix surface — proceed to Step 4. The fix commit (Step 5) will include the spec diff alongside the code change. |
| ❌ Dangling `x-lineage.process.*`                   | model is wrong. **Stall** (do not consume loop budget): set `stalled_reason: "harness closure failed: process gap — <detail>"`, refresh BOARD.md, point user at `/process <CAPABILITY_ID>`. |
| ❌ Dangling `x-lineage.bcm.*`                       | BCM is wrong. **Stall**: `stalled_reason: "harness closure failed: bcm gap — <detail>"`, point user at `reliever-knowledge`. |
| ❌ Missing controller / consumer                    | feed the gap into the failure list and loop back to Step 3.2 — same remediation cycle as a test failure. |

Stalls from process / bcm closure failures are deliberate: an upstream fix
cannot be done by `/fix` itself — the process model is authored upstream in
reliever-knowledge and consumed here read-only via `kpack process`, so it
cannot be amended from this repo at all.

---

## Step 4 — Re-Validate with the Matching Test Skill

After the implementation agent(s) finish, re-invoke the same test skill `/code`
would for this zone — it produces a fresh ephemeral environment of the same recipe
that the original test run used, so the fix is validated under the same conditions
as the failure that triggered `/fix`:

| Path | Test skill                  | Test agent                   | Ephemeral env recipe                                          |
|------|-----------------------------|-------------------------------|---------------------------------------------------------------|
| A    | `/test-business-capability` | `test-business-capability`   | `/tmp/test-{cap-id}-XXXXXX` — .NET service + MongoDB + RabbitMQ |
| C    | `/test-business-capability` | `test-business-capability`   | same as A (stub publishes to RabbitMQ; no MongoDB needed but harmless) |
| B    | `/test-app`                 | `test-app`                   | `/tmp/test-app-{cap-id}-XXXXXX` — static HTTP + BFF (+ RabbitMQ if needed) |

Pass to the test skill: the task ID, capability ID, zone, and `--branch` matching
`BRANCH_NAME` so it resolves artifacts from the correct worktree.

### If all tests pass

Proceed to Step 5 (commit + push to the existing branch).

### If tests still fail

Same loop semantics as `/code`:

```
IF loop_count >= max_loops → Stall Procedure (below)
ELSE
  loop_count += 1; persist; go back to Step 3.2 with the NEW failure list as
  FAILURE_BUNDLE — the previous block is replaced, not appended.
```

### Stall Procedure (loop budget exhausted)

Identical to `/code`'s stall: set `status: stalled`, write `stalled_reason` (loop
count + last failing items + date), refresh `/tasks/BOARD.md` via `/sort-task`,
report to the user, point them at `/continue-work TASK-NNN [--max-loops N]`.

`/fix` does not push the failed attempt — leave the worktree in place and the branch
untouched so the user can inspect.

---

## Step 5 — Commit and Push to the Existing Branch

After the test skill confirms green:

1. Inside `WORKTREE_PATH`, stage only the files touched by the fix (never `git add -A`).

2. Run repository sanity checks (same as `/code`):

   ```bash
   cd "$PROJECT_ROOT" && python tools/validate_repo.py
   cd "$PROJECT_ROOT" && python tools/validate_events.py
   ```

3. Commit with Conventional Commits — use `fix(TASK-NNN):` (or `fix(TASK-NNN)!:`
   if the fix changes a contract):

   ```bash
   git -C "$WORKTREE_PATH" commit -m "fix(TASK-NNN): <imperative subject ≤72 chars>

   <2–3 sentences: which failing item(s) this commit addresses, referenced by name>
   <Cite the failing CI step / test path / log line that motivated the fix>

   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
   ```

4. Push **to the same branch** (this updates the open PR in place):

   ```bash
   git -C "$WORKTREE_PATH" push origin "$BRANCH_NAME"
   ```

   Do **not** force-push unless the user explicitly asks. Do **not** open a new PR.
   Do **not** flip the task status (`in_review` stays `in_review`; `done` stays `done`
   if the fix is on a merged-then-broken branch — see "Special Cases" below).

5. If the PR has check runs, wait briefly and re-fetch:

   ```bash
   gh pr checks <PR_NUMBER> --watch --interval 30
   ```

   …or report to the user that CI was retriggered and the fix is on its way.

6. Append a comment to the PR describing what was done — concise, business
   language, list of fixed items:

   ```bash
   gh pr comment <PR_NUMBER> --body "$(cat <<'BODY'
   `/fix` applied to address failing checks:
   - ✅ <fixed item 1>
   - ✅ <fixed item 2>

   Validated locally by [test-business-capability | test-app] — [N]/[Total] criteria green.
   BODY
   )"
   ```

---

## Step 6 — Final Report

```
✅ TASK-[NNN] — fix pushed.
   Branch:   feat/TASK-NNN-{slug}        (existing branch, no new branch created)
   PR:       #N — comment appended, CI retriggered
   Loop:     [loop_count]/[max_loops]

Fixed items:
  ✅ <item 1>
  ✅ <item 2>

Test results: [N]/[Total] DoD criteria validated locally before push.

Worktree retained at /tmp/kanban-worktrees/TASK-NNN-{slug} until the PR is merged.
```

---

## Special Cases

| Situation | Behavior |
|-----------|----------|
| The PR was already merged (status: `done`) and `main` regressed | Same flow, but `BRANCH_NAME` resolves to a NEW branch named `fix/post-merge-TASK-NNN-{slug}` cut from current `main`. Open a fresh PR titled `fix(TASK-NNN): <subject>`. The TASK file's `pr_url` is added to a new line `fix_pr_urls:` (list) — the original `pr_url` stays intact. |
| The branch exists locally but the PR is closed (not merged) | Stop and ask the user: reopen the PR, cut a new one, or treat as the merged-regression case above. |
| No worktree, no local branch, only a remote branch | `git fetch origin <branch>:<branch>` then create the worktree on it. |
| `gh` is unavailable | Resolve branch from input directly; skip PR-comment / check-watch steps; report locally. |
| The failure looks like flake (timeouts, transient network) | Do NOT spawn an implementation agent. Tell the user to retry CI; if they confirm it's flake, exit without touching anything. |
| Multiple TASK-NNN branches share a PR | Refuse — `/fix` is one-task-at-a-time. Ask which task. |
| `task_type: contract-stub` task whose stub diverged from the schemas after a BCM update | Path C; the agent re-syncs schemas + stub. The TECH-TACT warning in the pack is acceptable (same as the original contract-stub flow). |

---

## Important Boundaries

- **Never create a new branch** when fixing an existing PR. The whole point of
  `/fix` is to push corrections onto the same branch so the PR is updated in place.
- **Never open a new PR** for an open PR's failures. Comment on the existing one.
- **Never force-push** without explicit user confirmation.
- **Never bypass tests.** The matching test skill is mandatory. If Playwright cannot
  install on Path B, fall back to `manual-checklist.md` exactly like `/test-app` does.
- **Never read `/bcm/`, `/func-adr/`, `/adr/`, `/strategic-vision/`,
  `/domain-vision/`, or `/tech-vision/` directly.** Use `kpack`.
- **One task per invocation.** Refuse compound requests; ask which to fix first.
- **Loop budget is shared with `/code`.** A task that already burned 8 of 10 loops in
  `/code` only has 2 loops left in `/fix`.
