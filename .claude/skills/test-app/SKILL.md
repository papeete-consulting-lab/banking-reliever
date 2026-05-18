---
name: test-app
description: >
  Entry-point that dispatches a test-app agent run for a CHANNEL-zone TASK-NNN.
  Resolves the task, the active branch/environment, locates the artifacts
  produced by the code-web-frontend and create-bff agents (frontend under
  sources/{CAP_ID}/frontend/, BFF under sources/{CAP_ID}/bff/),
  then spawns the test-app agent (a senior test engineer specialized in
  vanilla web frontends + .NET BFF) to generate, run, and report tests
  against the Definition of Done, FUNC ADR rules, plan scoping, and
  product/strategic vision. Tests run in an ephemeral local environment —
  no modification of the original artifacts.

  This skill targets CHANNEL-zone tasks only. For non-CHANNEL tasks
  (backend microservices produced by the implement-capability agent),
  use /test-business-capability instead.

  Supports `--branch <slug>` or `--env <slug>` to resolve artifacts from
  a specific worktree, and `--bff` to force BFF mode (auto-detected
  otherwise).

  Trigger this skill whenever the user says: "test-app", "test the app",
  "test the frontend", "test the BFF", "test the channel", "validate the
  dashboard", "test the web view", "verify the UI", "test on branch X",
  "test on env X", or any phrasing requesting automated validation of a
  CHANNEL-zone task or web application. Also trigger proactively after a
  code-web-frontend or create-bff agent has finished and the user wants to
  validate the result.
---

# Test App — Entry Point

This skill is the user-facing entry point for testing a CHANNEL-zone TASK
(frontend + BFF). The actual reasoning, test generation, execution, and
verdict are delegated to the **`test-app` agent**
(`.claude/agents/test-app.md`), which operates as a senior test engineer
specialized in vanilla web frontends and .NET 10 Minimal API BFFs.

Your responsibility here is narrow: identify the task, confirm it is
CHANNEL, resolve the branch/environment, validate prerequisites, hand the
agent everything it needs to do its job, and relay its verdict to the user.

For non-CHANNEL tasks (backend microservices), redirect to
`/test-business-capability`.

---

## Step 1 — Identify the Task

The user provides a `TASK-NNN` identifier or a capability name. Optional flags:

| Flag | Effect |
|------|--------|
| `--branch <slug>` | Resolve artifacts from a named git branch's worktree |
| `--env <slug>` | Same as `--branch` (alias, environment-slug convention) |
| `--bff` | Force BFF testing mode (auto-detected otherwise) |

If the task identifier is ambiguous, list tasks with status `done` or
`in_progress` from `tasks/*/` — only already-implemented tasks can be
tested. If nothing matches, stop and ask.

---

## Step 2 — Confirm CHANNEL Zone

Read the capability ID from the TASK file frontmatter, then look up its
zoning:

```bash
CAP_ID=$(grep -m1 '^capability_id:' "/tasks/{capability-id}/TASK-NNN-*.md" | awk '{print $2}')

# Find the YAML that declares this capability
ZONING=$(grep -l "id: ${CAP_ID}" bcm/capabilities-*.yaml 2>/dev/null \
  | xargs grep -A1 "id: ${CAP_ID}" 2>/dev/null \
  | grep -m1 'zoning:' \
  | awk '{print $2}')

echo "Capability ${CAP_ID} — zone: ${ZONING}"
```

If `ZONING` is not `CHANNEL`, stop and tell the user:

> "TASK-NNN belongs to ${CAP_ID} (zone: ${ZONING}), which is not a CHANNEL
> capability. Use `/test-business-capability TASK-NNN` to test backend
> microservices. The `/test-app` skill only handles frontend + BFF
> artifacts."

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

`BRANCH` scopes BFF port lookup (`.env.local`) and artifact discovery when
multiple branches co-exist on the same machine.

---

## Step 4 — Verify Artifacts Exist

Quick existence check before spawning the agent (cheaper than letting the
agent fail):

```bash
FRONTEND="sources/${CAP_ID}/frontend"
BFF_DIR="sources/${CAP_ID}/bff"

[ -d "$FRONTEND" ] || [ -d "$BFF_DIR" ] \
  || { echo "✗ No CHANNEL artifact found for $CAP_ID — run /code TASK-NNN first."; exit 1; }
```

If nothing exists, stop and tell the user:

> "No CHANNEL implementation found for TASK-NNN (no frontend under
> `sources/{CAP_ID}/frontend/` and no BFF under
> `sources/{CAP_ID}/bff/`). Run `/code TASK-NNN` first."

If a BFF directory exists but `.env.local` is missing, surface that as a
gap before spawning — `create-bff` did not finish.

---

## Step 5 — Spawn the test-app Agent

Hand the agent a self-contained context block — it will not see this
conversation. Include:

- The TASK identifier (`TASK-NNN`) and full path to the TASK file
- The resolved `BRANCH` value
- The capability ID and confirmed zone (CHANNEL)
- The list of artifacts located in Step 4 (frontend / BFF paths)
- Any flags the user passed (`--bff`, `--env`, etc.)
- The roadmap path: `/roadmap/{capability-id}/roadmap.md` (local artifact)
- An explicit instruction to fetch BCM/ADR/vision context from `bcm-pack`:
  `bcm-pack pack <CAPABILITY_ID> --deep --compact` — and to NOT read
  `/bcm/`, `/func-adr/`, `/adr/`, `/tech-adr/`, `/tech-vision/`,
  `/strategic-vision/`, or `/product-vision/` directly. The FUNC ADR is
  in `slices.capability_definition`; the tactical ADR is in
  `slices.tactical_stack`; vision narratives are in
  `slices.product_vision` / `slices.business_vision` / `slices.tech_vision`.

Spawn:

```
Agent({
  subagent_type: "test-app",
  description: "Test TASK-NNN — [short title]",
  prompt: <full context block as described above>
})
```

Say to the user:

> "Spawning test-app agent for TASK-NNN (branch: {BRANCH})..."

The agent handles everything from here:
- Reads context: TASK file (local) + plan (local) + capability pack via `bcm-pack` (FUNC ADR, tactical ADR, vision narratives)
- States its test plan + assumptions
- Picks the test mode (full-mock / frontend+bff / bff-only)
- Brings up the ephemeral environment (HTTP server + BFF + RabbitMQ if needed)
- Generates the test corpus under `tests/{capability-id}/TASK-NNN-{slug}/`
- Runs pytest
- Tears down the environment
- Returns a structured verdict (✅/❌ per criterion in business language)

The agent may push back if the context is incoherent (no DoD, missing FUNC
ADR, artifacts paired to the wrong capability, tooling unavailable, BFF
won't start). Surface that to the user as the gap to resolve — do not
retry blindly.

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

- **CHANNEL zone only.** Non-CHANNEL tasks must be redirected to
  `/test-business-capability`.
- **This skill does not write tests** — it delegates to the agent.
- **This skill does not modify any artifact** — neither the things under test
  nor the TASK file. Status transitions are the responsibility of `/code` or
  `/launch-task`, not of the test entry point.
- **This skill does not iterate on remediation** — the test verdict is one
  shot. The remediation loop lives in `/code`.
- One TASK at a time — to test multiple tasks, invoke this skill once per
  task (or use `/launch-task` which handles batching).
