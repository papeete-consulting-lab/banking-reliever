---
name: test-business-capability
description: >
  Entry-point that dispatches a test-business-capability agent run for a
  non-CHANNEL TASK-NNN. Resolves the task, the active branch/environment,
  locates the .NET microservice produced by the implement-capability agent
  under sources/{capability-name}/backend/, then spawns the
  test-business-capability agent (a senior test engineer specialized in
  event-driven .NET microservices) to generate, run, and report tests
  against the Definition of Done, FUNC ADR rules, plan scoping, and
  product/strategic vision. Tests run in an ephemeral local environment
  (the .NET service + its MongoDB + RabbitMQ via docker-compose) — no
  modification of the original artifacts.

  This skill targets non-CHANNEL zones only (BUSINESS_SERVICE_PRODUCTION,
  SUPPORT, REFERENTIAL, EXCHANGE_B2B, DATA_ANALYTICS, STEERING). For
  CHANNEL-zone tasks (frontend + BFF produced by code-web-frontend +
  create-bff), use /test-app instead.

  Supports `--branch <slug>` or `--env <slug>` to resolve artifacts from a
  specific worktree.

  Trigger this skill whenever the user says: "test-business-capability",
  "test the microservice", "test the backend", "test the API", "test the
  domain service", "verify the events emitted", "test CAP. backend", "test
  on branch X" (for a non-CHANNEL capability), or any phrasing requesting
  automated validation of a backend microservice. Also trigger proactively
  after the implement-capability agent has finished and the user wants to
  validate the result.
---

# Test Business Capability — Entry Point

This skill is the user-facing entry point for testing a non-CHANNEL TASK
(backend microservice). The actual reasoning, test generation, execution,
and verdict are delegated to the **`test-business-capability` agent**
(`.claude/agents/test-business-capability.md`), which operates as a senior
test engineer specialized in event-driven .NET microservices.

Your responsibility here is narrow: identify the task, confirm it is
non-CHANNEL, resolve the branch/environment, validate prerequisites, hand
the agent everything it needs to do its job, and relay its verdict to the
user.

For CHANNEL-zone tasks (frontend + BFF), redirect to `/test-app`.

---

## Step 1 — Identify the Task

The user provides a `TASK-NNN` identifier or a capability name. Optional flags:

| Flag | Effect |
|------|--------|
| `--branch <slug>` | Resolve artifacts from a named git branch's worktree |
| `--env <slug>` | Same as `--branch` (alias, environment-slug convention) |

If the task identifier is ambiguous, list tasks with status `done` or
`in_progress` from `tasks/*/` — only already-implemented tasks can be
tested. If nothing matches, stop and ask.

---

## Step 2 — Confirm non-CHANNEL Zone

Read the capability ID from the TASK file frontmatter, then look up its
zoning:

```bash
CAP_ID=$(grep -m1 '^capability_id:' "/tasks/{capability-id}/TASK-NNN-*.md" | awk '{print $2}')

ZONING=$(grep -l "id: ${CAP_ID}" bcm/capabilities-*.yaml 2>/dev/null \
  | xargs grep -A1 "id: ${CAP_ID}" 2>/dev/null \
  | grep -m1 'zoning:' \
  | awk '{print $2}')

echo "Capability ${CAP_ID} — zone: ${ZONING}"
```

If `ZONING` is `CHANNEL`, stop and tell the user:

> "TASK-NNN belongs to ${CAP_ID} which is a CHANNEL capability. Use
> `/test-app TASK-NNN` to test the frontend + BFF artifacts. The
> `/test-business-capability` skill only handles backend microservices."

---

## Step 3 — Resolve Branch / Environment

```bash
# Use --branch / --env if given; otherwise detect from current git state.
if [ -n "${BRANCH_FLAG:-}" ]; then
  BRANCH="$BRANCH_FLAG"
else
  BRANCH=$(git branch --show-current 2>/dev/null \
    | tr '[:upper:]' '[:lower:]' \
    | sed 's/[^a-z0-9]/-/g; s/-\+/-/g; s/^-\|-$//g')
fi
echo "Active branch/environment: $BRANCH"
```

`BRANCH` scopes RabbitMQ exchange/queue names and OTel `environment` tags,
preventing concurrent worktrees from colliding on infrastructure.

---

## Step 4 — Verify Artifacts Exist

Quick existence check before spawning the agent (cheaper than letting the
agent fail):

```bash
BACKEND_DIR=$(ls -d sources/*/backend 2>/dev/null | head -1)

[ -n "$BACKEND_DIR" ] && [ -f "$BACKEND_DIR"/*.sln ] \
  || { echo "✗ No backend artifact found — run /code TASK-NNN first."; exit 1; }
```

If nothing exists, stop and tell the user:

> "No backend implementation found for TASK-NNN under
> `sources/{cap-name}/backend/`. Run `/code TASK-NNN` first."

---

## Step 5 — Spawn the test-business-capability Agent

Hand the agent a self-contained context block — it will not see this
conversation. Include:

- The TASK identifier (`TASK-NNN`) and full path to the TASK file
- The resolved `BRANCH` value
- The capability ID and confirmed zone (non-CHANNEL)
- The backend artifact path located in Step 4
- Any flags the user passed (`--env`, etc.)
- The roadmap path: `/roadmap/{capability-id}/roadmap.md` (local artifact)
- An explicit instruction to fetch BCM/ADR/vision context from `bcm-pack`:
  `bcm-pack pack <CAPABILITY_ID> --deep --compact` — and to NOT read
  `/bcm/`, `/func-adr/`, `/adr/`, `/tech-adr/`, `/tech-vision/`,
  `/strategic-vision/`, or `/product-vision/` directly. The FUNC ADR is
  in `slices.capability_definition`; the tactical ADR is in
  `slices.tactical_stack`; vision narratives are in
  `slices.product_vision` / `slices.business_vision` / `slices.tech_vision`.
- Local stack metadata if the implement-capability agent persisted it
  (`LOCAL_PORT`, derived MongoDB / RabbitMQ ports)

Spawn:

```
Agent({
  subagent_type: "test-business-capability",
  description: "Test TASK-NNN — [short title]",
  prompt: <full context block as described above>
})
```

Say to the user:

> "Spawning test-business-capability agent for TASK-NNN (branch: {BRANCH})..."

The agent handles everything from here:
- Reads context: TASK file (local) + plan (local) + capability pack via `bcm-pack` (FUNC ADR, tactical ADR, vision narratives, BCM data)
- States its test plan + assumptions
- Brings up the ephemeral environment (.NET service + MongoDB + RabbitMQ)
- Generates the test corpus under `tests/{capability-id}/TASK-NNN-{slug}/`
- Runs pytest (REST endpoints, persistence, event emission)
- Tears down the environment
- Returns a structured verdict (✅/❌ per criterion in business language)

The agent may push back if the context is incoherent (no DoD, missing FUNC
ADR, artifacts paired to the wrong capability, tooling unavailable,
RabbitMQ won't start, GitHub NuGet credentials missing). Surface that to
the user as the gap to resolve — do not retry blindly.

---

## Step 6 — Relay the Verdict

Forward the agent's report to the user verbatim — its format
(`═══` block with per-criterion verdicts, score, report path, logs path) is
already business-readable. Append a one-line next-step pointer if relevant:

- All green → "✅ All DoD criteria validated. Ready to push the PR."
- Some red → "⚠ {N} criteria failed. The remediation loop in `/code` will
  pick this up if invoked from there, otherwise fix and re-run."
- Cannot proceed → "✗ Cannot test — see gap above. Resolve before retrying."

Do not modify the agent's verdict — the per-criterion mapping is what the
caller (often `/code`'s remediation loop) parses.

---

## Boundaries

- **Non-CHANNEL zones only.** CHANNEL tasks must be redirected to
  `/test-app`.
- **This skill does not write tests** — it delegates to the agent.
- **This skill does not modify any artifact** — neither the things under test
  nor the TASK file. Status transitions are the responsibility of `/code` or
  `/launch-task`, not of the test entry point.
- **This skill does not iterate on remediation** — the test verdict is one
  shot. The remediation loop lives in `/code`.
- One TASK at a time — to test multiple tasks, invoke this skill once per
  task (or use `/launch-task` which handles batching).
