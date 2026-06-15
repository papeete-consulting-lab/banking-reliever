---
name: code
description: >
  Triggers the implementation of a specific task by reading its task file and invoking the 
  right implementation skill(s) based on the capability zone, then validates the result 
  with the matching test skill (test-business-capability for backend, test-app for 
  frontend+BFF). Use this skill whenever the user wants to implement a 
  task, code a specific capability task, start development on a TASK-NNN, or execute an 
  implementation work item. Trigger on: "code TASK-NNN", "implement TASK-NNN", 
  "code this task", "start implementing", "build [capability]", or any time a task file 
  exists in /tasks/{capability}/ with status "todo" and all dependencies are resolved. 
  Also trigger proactively when the user says "let's code" or "start development" and a 
  specific task or capability is named.
---

# Code Skill

You are the bridge between the planning world and the implementation world. Your job is to
read a task file, understand what it asks for in business terms, detect the capability zone,
invoke the right implementation skill(s), then validate the result with the test skill —
repeating until the Definition of Done is fully satisfied.

---

## Sentinel — acquire before writing TASK cards

A PreToolUse hook (`tasks-folder-guard.py`) rejects every Write/Edit/MultiEdit/
NotebookEdit call targeting `tasks/<CAP>/TASK-*.md` unless the shared
task-pipeline sentinel `/tmp/.claude-task-pipeline.active` is present and
≤30 min old. This skill is on the allowlist (together with `/task`,
`/task-refinement`, `/launch-task`, `/fix`, `/continue-work`, and
`/pr-merge-watcher`). The implementation agents this skill spawns
(`implement-capability`, `implement-capability-python`, `create-bff`,
`code-web-frontend`) never touch TASK cards directly — they return verdicts
that this skill applies (loop_count, max_loops, pr_url, stalled_reason,
status transitions).

Before the first TASK-card write:

```bash
touch /tmp/.claude-task-pipeline.active
```

At the very end (success or graceful abort):

```bash
rm -f /tmp/.claude-task-pipeline.active
```

A `/code` session typically spans more than 30 minutes — re-`touch` the
sentinel just before each TASK-card edit (especially after a long
sub-agent invocation, after the test skill completes, and before the
final status transition to `in_review`/`stalled`). A stale sentinel grants
write access to the next agent — explicit `rm -f` on exit is preferred.

> BOARD.md is **not** guarded by this sentinel. `/code` reflects its
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

The process model is the **contract** that the implementation must satisfy.
This skill, and every agent it spawns (`implement-capability`,
`implement-capability-python`, `create-bff`, `code-web-frontend`), consumes it
via `kpack process <CAP_ID>` but never reshapes it. If a remediation
iteration suggests changing a command shape, an aggregate invariant, or a
routing key, stop the loop and tell the user to run `/process <CAPABILITY_ID>`
in the reliever-knowledge repo to update the model — then re-run `/code TASK-NNN`.

When forwarding context to `implement-capability`, `create-bff`, or
`code-web-frontend`, instruct each agent to **fetch** the process model via
`kpack process <CAPABILITY_ID>` (the `.model.<stem>` slices and the
`.schemas[...]` JSON Schemas) as the source of truth on aggregates, commands,
events, and routing keys — never to invent or reshape them.

---

## Readiness gate — the process model must resolve via `kpack process`

Before reading the task, before spawning any agent, verify the capability's
process model resolves. A model is ready iff `kpack process <CAP_ID>`
returns exit 0 (kpack resolves the published `main` of reliever-knowledge by
default):

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
CAP_ID="<CAPABILITY_ID-of-the-task>"

# The process model lives in reliever-knowledge now; it is ready iff kpack
# can resolve it (kpack resolves the published main by default).
if ! kpack process "$CAP_ID" --compact >/tmp/process-model.json 2>/tmp/process-model.err; then
  echo "GATE-FAIL: no process model for $CAP_ID."
  echo "Run /process $CAP_ID in the reliever-knowledge repo and merge its PR, then retry."
  cat /tmp/process-model.err
  exit 1
fi
```

If the gate fails, **stop and surface the failure** — do not spawn any
implementation agent. Once `/process <CAP_ID>` is run in the reliever-knowledge
repo and its PR merged, re-run `/code TASK-NNN`.

---

## Before You Begin

> **Note:** For orchestrated multi-task workflows (board view, prioritization, dependency
> tracking), use the `/launch-task` skill instead — it calls this skill at the right moment.

1. **Identify the task.** The user should specify a task ID (e.g., `TASK-001`) or a capability
   name. If ambiguous, redirect to `/launch-task` to get the prioritized list.

2. **Read the task file.** Find it at `/tasks/{capability-id}/TASK-NNN-*.md`.

3. **Verify prerequisites:**
   - Status is `todo` or `in_progress` (not `in_review`, `done`, or `stalled`)
   - If status is `stalled`: stop and tell the user to run `/continue-work TASK-NNN` first.
   - All tasks in `depends_on` have status `done`
   - No open questions in the task file are unresolved

   If any prerequisite fails, stop and explain:
   > "TASK-NNN cannot start because [reason]. Resolve this first."

4. **Read supporting context.** All BCM/ADR/vision knowledge comes from the `kpack` 
   engine — never read `/bcm/`, `/func-adr/`, `/adr/`, `/strategic-vision/`, or `/domain-vision/`
   directly:

   ```bash
   kpack pack <CAPABILITY_ID> --compact > /tmp/pack-code.json
   ```

   Selective slice usage at this layer (this skill is mostly a router — keep it light):

   | Slice                       | Used by /code itself                          |
   |-----------------------------|-----------------------------------------------|
   | `capability_self`           | zone detection, capability_name, level        |
   | `capability_definition`     | summarized to the user in Step 1, forwarded to the spawned agent |
   | `emitted_events[] \| select(.layer=="business")`  | "events that will become emittable" in Step 1 |
   | `consumed_events[] \| select(.layer=="business")` | "events consumed (BFF subscriptions)" in Step 1 (CHANNEL only) |

   The deeper slices (tactical_stack, governing_*, vision narratives) are forwarded to the
   spawned agent via the prompt — that agent re-fetches them with `--deep` if it needs the
   narratives.

   Supporting artifacts:
   - the roadmap file at `/roadmap/{capability-id}/roadmap.md` (local, read directly)
   - the Process Modelling layer via `kpack process <CAPABILITY_ID> --compact`
     (read-only) — the `.model.aggregates`, `.model.commands`, `.model.policies`,
     `.model["read-models"]`, `.model.bus`, `.model.api` slices (use `.parsed`,
     fallback `.raw` when null) and the `.schemas[...]` JSON Schemas. The
     implementation agents consume these via `kpack process`; they do not
     author or modify them.

5. **Read loop counters** from the task file frontmatter:
   - `loop_count`: number of remediation iterations already used (default `0` if absent)
   - `max_loops`: maximum allowed iterations (default `10` if absent)

   If the task file does not yet have these fields, treat them as `loop_count: 0` /
   `max_loops: 10` and write them to the frontmatter before proceeding:
   ```yaml
   loop_count: 0
   max_loops: 10
   ```

6. **Detect the routing path.** Three signals are inspected, in order:

   **6a — `task_type` frontmatter (highest priority)**

   Read the `task_type` field from the TASK frontmatter. If set to
   `contract-stub`, take **Path C** regardless of zone:

   | `task_type` value | Routing path | Notes |
   |-------------------|--------------|-------|
   | `contract-stub`   | **Path C — Contract+Stub** | spawns the matching `implement-capability*` agent in **Mode B** — a minimal host materialising the full consumer-facing surface: an event publisher emitting `BNK.RLVR.RVT.*` on RabbitMQ AND an HTTP server serving the operations declared in the model's `api` surface (`kpack process <CAP_ID>` → `.model.api`) with canned fixtures. Either half may be empty when its source YAML declares nothing. The language of the host (.NET vs Python) is decided in **6c** below. |
   | (absent) or `full-microservice` | Fall through to 6b | standard zone-aware routing |

   **6b — Zone (when `task_type` does not force Path C)**

   Detect the zone from the pack's `slices.capability_self[0].zoning` (or fall back to 
   `slices.capability_definition[0].decision_scope.zoning` from the FUNC ADR if absent).
   Never read `bcm/capabilities-*.yaml` directly. Map the value as follows:

   | YAML `zoning` value          | Zone family       | Implementation path |
   |------------------------------|-------------------|---------------------|
   | `BUSINESS_SERVICE_PRODUCTION`| Core domain       | **Path A** — `implement-capability*` (Mode A — full microservice; language picked in 6c) |
   | `SUPPORT`                    | Transverse IT     | Path A — `implement-capability*` (Mode A) |
   | `REFERENTIAL`                | Master data       | Path A — `implement-capability*` (Mode A) |
   | `EXCHANGE_B2B`               | Ecosystem B2B     | Path A — `implement-capability*` (Mode A) |
   | `DATA_ANALYTICS`             | Data / BI / AI    | Path A — `implement-capability*` (Mode A) |
   | `STEERING`                   | Pilotage          | Path A — `implement-capability*` (Mode A) |
   | `CHANNEL`                    | Omnichannel       | **Path B** — `create-bff` + `code-web-frontend` (parallel) — language is fixed (.NET BFF + vanilla JS frontend); skip 6c |

   **6c — Language (TECH-TACT-driven, Path A & Path C only)**

   For Path A and Path C, inspect the **tactical_stack** slice of the
   `kpack` output to pick the concrete implementation agent. The
   TECH-TACT ADR (`ADR-TECH-TACT-{NNN}`) is authored per L2 capability
   and pins the runtime; its `tags` array carries the language signal:

   ```bash
   python3 - <<'PY'
   import json, sys
   p = json.load(open('/tmp/pack-code.json'))
   stack = p['slices'].get('tactical_stack', [])
   if not stack:
       print("LANG=UNKNOWN")
       print("REASON=no-tech-tact-adr")
       sys.exit(0)
   tags = {t.lower() for t in stack[0].get('tags', [])}
   if tags & {"python", "fastapi", "starlette"}:
       print("LANG=python")
   elif tags & {"dotnet", ".net", "csharp", "aspnet"}:
       print("LANG=dotnet")
   else:
       print("LANG=UNKNOWN")
       print(f"REASON=no-language-tag tags={sorted(tags)}")
   PY
   ```

   Map the result to an agent:

   | `LANG` value | Agent (`subagent_type`)       | Output root                                 |
   |--------------|-------------------------------|---------------------------------------------|
   | `python`     | `implement-capability-python` | `sources/{capability-name}/backend/` (Mode A) or `sources/{capability-name}/stub/` (Mode B) — Python package layout |
   | `dotnet`     | `implement-capability`        | `sources/{capability-name}/backend/` (Mode A) or `sources/{capability-name}/stub/` (Mode B) — .NET 10 solution |
   | `UNKNOWN`    | `implement-capability` (fallback) | as above — **and** surface the warning below to the user |

   Fallback warning (only when `LANG=UNKNOWN`):

   > ⚠ No TECH-TACT ADR (or no language tag) found for `{CAP_ID}`. Falling
   > back to the .NET `implement-capability` agent. To change the runtime,
   > author `ADR-TECH-TACT-{NNN}` in `reliever-knowledge` with a `tags:`
   > list that names the language (`python`, `dotnet`, …) and merge it
   > upstream; `/code` will re-route on the next run.

   The selected agent re-validates the tag on entry (its step 0.6) and
   refuses to scaffold a mismatch — that is a defence-in-depth check, not
   a substitute for getting the routing right here.

   **Summary** — three routing paths × two languages:
   - **Path C** (Contract+Stub) — triggered by `task_type: contract-stub`, any zone; language picked in 6c
   - **Path A** (Full microservice) — non-CHANNEL zone, `task_type` unset / `full-microservice`; language picked in 6c
   - **Path B** (BFF + Frontend) — CHANNEL zone, `task_type` unset / `full-microservice`; language fixed (.NET BFF + vanilla JS)

---

## Step 0 — Create Isolation Branch

Before writing any code, create a dedicated branch and verify the git state:

```bash
# Ensure we are on main and the tree is clean
git status --porcelain
git checkout main 2>/dev/null || git checkout master 2>/dev/null

# Derive the branch name from the task ID and title (kebab-case)
TASK_ID="TASK-NNN"                          # e.g. TASK-003
TASK_SLUG="<title-in-kebab-case>"           # e.g. beneficiary-dashboard
BRANCH_NAME="feat/${TASK_ID}-${TASK_SLUG}"  # e.g. feat/TASK-003-beneficiary-dashboard

git checkout -b "$BRANCH_NAME"
```

Report to the user:
> "Working on branch `feat/TASK-NNN-{slug}`. All changes will be isolated here until the PR is opened."

If the repository has no commits yet (`git log` fails), skip the `git checkout main` step and
simply run `git checkout -b "$BRANCH_NAME"` from the initial state.

---

## Step 1 — Summarize What Will Be Built

Before invoking any implementation skill, present a clear summary to the user.

**For non-CHANNEL zones:**

```
Ready to implement TASK-[NNN]: [Title]

Capability: [Name] ([ID]) — [Zone]
Epic: [Epic N — Name]

What will be built:
[2-3 sentences from the task's "What to Build" section, in plain language]

Business events that will become emittable:
- [EventName]
- [EventName]

Definition of Done:
- [ ] [condition 1]
- [ ] [condition 2]

Implementation path: implement-capability (.NET microservice)

Shall I proceed?
```

**For CHANNEL zone:**

```
Ready to implement TASK-[NNN]: [Title]

Capability: [Name] ([ID]) — CHANNEL zone
Epic: [Epic N — Name]

What will be built:
[2-3 sentences from the task's "What to Build" section, in plain language]

Events consumed (BFF subscriptions):
- [EventName] from [EmittingCapabilityId]

Events produced:
- [EventName]

Definition of Done:
- [ ] [condition 1]
- [ ] [condition 2]

Implementation path: create-bff + code-web-frontend (launched in parallel)
After implementation: test-app will validate all DoD criteria.

Shall I proceed?
```

Wait for the user's confirmation before proceeding.

---

## Step 2 — Invoke the Implementation Component(s)

### Path C — Contract+Stub (`task_type: contract-stub`, any zone)

Spawn the language-matching agent (from step 6c —
`implement-capability` for `.NET`, `implement-capability-python` for
Python) in **Mode B** via the `Agent` tool. The agent itself reads the
`task_type` from the TASK file and switches to Mode B accordingly —
your job here is just to feed it the right context.

The context to pass includes:

- The capability ID, name, zone, and level
- An explicit mention that `task_type: contract-stub` is set (so the agent
  knows which mode to take, even before reading the file)
- The governing FUNC ADR(s)
- The events to contract (the BNK.RLVR.EVT/BNK.RLVR.RVT pairs named in the task) — drives
  the publisher half
- The query operations to stub — every entry in the process model's api slice
  (`kpack process <CAP_ID>` → `.model.api`), with their response schemas.
  Drives the HTTP half.
- The carried business objects / resources (event payloads + canned
  fixture shapes)
- `ADR-TECH-STRAT-001` content (or pointer + summary) — the agent needs the
  bus topology rules to scaffold the publisher half correctly
- `ADR-TECH-STRAT-003` content (or pointer + summary) — the agent needs
  the REST conventions to scaffold the query half correctly
- The DoD with its versioning encoding, cadence range, fixture count
  requirement, and validation site conventions

Use:
```
Agent({
  subagent_type: "<implement-capability | implement-capability-python>",   // from step 6c
  description: "Contract+stub for [capability name]",
  prompt: <full context block including the task_type signal,
           the LANG resolved in step 6c (so the agent's own check
           matches), the TECH-TACT ADR id and tags,
           BCM YAML excerpts for the events to contract,
           ADR-TECH-STRAT-001 rules, DoD>
})
```

Say:
> "Spawning [implement-capability | implement-capability-python] agent in Mode B (contract+stub) for [capability name] with task TASK-[NNN]..."

The agent produces:
- A single minimal .NET host under `sources/{capability-name}/stub/`,
  combining a `BackgroundService` event publisher (when the process model's
  `.model.bus` slice is non-empty) and an ASP.NET Core Minimal-API query
  server (when its `.model.api` slice is non-empty)
- Canned fixtures under `sources/{capability-name}/stub/fixtures/`
  (≥3 per query operation, deterministic IDs)
- The wire-format JSON Schemas it consumes are NOT regenerated — the
  agent reads them from the `kpack process <CAP_ID>` envelope's
  `.schemas[...]` (already authored by `/process` in reliever-knowledge). No
  schema files are authored by the stub.
- No full microservice scaffold (Domain / Application / Infrastructure /
  Presentation / Contracts projects), no MongoDB, no domain model

The agent may push back if the capability has **no consumer-facing
surface at all** (both `bus.yaml` and `api.yaml` empty), if
`ADR-TECH-STRAT-001` is missing while events are declared, or if the
FUNC ADR contradicts the task. Surface that to the user as the gap
to resolve.

---

### Path A — Non-CHANNEL zones (BUSINESS_SERVICE_PRODUCTION, SUPPORT, REFERENTIAL, EXCHANGE_B2B, DATA_ANALYTICS, STEERING)

> Use this path **only** when `task_type` is absent or `full-microservice`.
> If `task_type: contract-stub`, use **Path C** above instead, regardless of zone.

Spawn the language-matching agent (from step 6c) via the `Agent` tool
with the full task context assembled as input. The context to pass
includes:

- The capability ID, name, zone, and level
- The **TECH-TACT ADR id** and its `tags` (so the agent can confirm
  the routing on entry)
- The `LANG` value resolved in step 6c (`python` or `dotnet`)
- The governing FUNC ADR(s)
- The business events to implement (names and trigger conditions)
- The business objects involved
- The event subscriptions required
- The Definition of Done

Use (with `subagent_type` set from step 6c):
```
Agent({
  subagent_type: "<implement-capability | implement-capability-python>",
  description: "Scaffold [capability name] ([LANG])",
  prompt: <full context block as described above>
})
```

Say:
> "Spawning [implement-capability | implement-capability-python] agent for [capability name] (LANG=[python|dotnet]) with task TASK-[NNN]..."

Both agents share the same decision framework — hexagonal /
Clean-Architecture layering, DDD aggregates, explicit assumption block,
read-only `process/` contract, Mode A / Mode B split — and differ only
in the emitted artefacts:

| Agent                          | Stack defaults                                          | Output language       |
|--------------------------------|---------------------------------------------------------|-----------------------|
| `implement-capability`         | .NET 10, ASP.NET Core, MongoDB, RabbitMQ (MassTransit)  | C#                    |
| `implement-capability-python`  | Python 3.12+, FastAPI, motor (MongoDB) or psycopg/asyncpg (PostgreSQL when ADR tags `postgresql`), aio-pika | Python                |

The chosen agent exercises judgment on aggregates, ports, bus topology,
and library pinning from the FUNC + TECH-TACT ADRs. Your job here is to
feed it the right business context from the task file. The agent may
push back if the context is incoherent (missing FUNC ADR, cross-zone
task, stack mismatch — including a Python agent invoked on a `.NET`-tagged
capability or vice-versa); surface that to the user as the gap to resolve.

---

### Path B — CHANNEL zone

> Use this path **only** when `task_type` is absent or `full-microservice`
> and the zone is `CHANNEL`. If `task_type: contract-stub`, use **Path C**
> above instead.

Spawn **both** the `create-bff` and `code-web-frontend` agents **in parallel**
(send both `Agent` tool calls in a single message — they are independent and
run concurrently in the same isolated worktree):

1. **`create-bff` agent** — senior backend engineer that scaffolds the .NET 10 BFF
   aggregating upstream events from RabbitMQ and exposing REST endpoints per L3
   sub-capability. The agent reasons from the FUNC ADR + tactical ADRs and makes
   explicit decisions on L3 endpoints, event topology, ports, and ETag strategy.

   Use:
   ```
   Agent({
     subagent_type: "create-bff",
     description: "Scaffold BFF for [capability name]",
     prompt: <full context block: L2 capability ID, FUNC ADR content (L3 list,
              events consumed with emitting L2, events produced, dignity rules),
              tactical ADRs from tech-adr/, Definition of Done, task identifier>
   })
   ```

2. **`code-web-frontend` agent** — senior frontend engineer that generates the
   vanilla HTML/CSS/JS web view from the task plan, FUNC ADRs, domain vision,
   and the BFF API contract (or inferred contract if the BFF is not yet compiled).
   The agent decides on views, sections, stub data, dignity-rule DOM order, and
   testability hooks.

   Use:
   ```
   Agent({
     subagent_type: "code-web-frontend",
     description: "Scaffold frontend for [capability name]",
     prompt: <full context block: task identifier and task file content,
              capability ID, FUNC ADR content, domain vision excerpts,
              instruction to read sources/{CAP_ID}/bff/ for the API contract —
              or to infer it from endpoint paths derived by the create-bff
              agent if the BFF is not yet written, Definition of Done>
   })
   ```

Say:
> "Spawning create-bff and code-web-frontend agents in parallel for [capability name] — CHANNEL zone..."

Wait for **both** agents to complete before proceeding to Step 3. Either agent
may push back if its context is incoherent (capability not in CHANNEL zone,
missing FUNC ADR, output dir already populated, unsupported stack); surface
that to the user as the gap to resolve.

---

## Step 2.5 — Add the contract harness (Path A only)

> **Skip this step for Path B (CHANNEL).** The BFF already enforces its own
> contract surface via `create-bff`. A future `harness-bff` skill will extend
> the same lineage pattern there.
>
> **Skip this step for Path C (contract-stub).** Mode B's scaffold is a
> minimal host (event publisher + canned-fixture query API); the full
> OpenAPI/AsyncAPI harness with bidirectional lineage is overkill for
> that scaffold. Re-introduce when the contract-stub matures into a full
> microservice (which will route back through Path A and trigger Step 2.5).

After the language-matching agent (`implement-capability` or
`implement-capability-python`) succeeds for a non-CHANNEL task, invoke
the `/harness-backend` skill to add the contract harness to the
freshly-scaffolded microservice. The harness derives its specs from the process
model (consumed via `kpack process <CAP_ID>`; the `process/{capability-id}/…`
names below are stable logical provenance references) and `kpack` — it is
language-agnostic and works on both .NET and Python services. The harness
produces, under `sources/{capability-name}/backend/contracts/specs/`:

- `openapi.yaml` (OpenAPI 3.1) — derived strictly from
  `process/{capability-id}/api.yaml` + `commands.yaml` + `read-models.yaml` +
  `schemas/CMD.*.schema.json` + `kpack`'s `.slices.carried_objects[] | select(.layer=="resource")` (resource shapes).
- `asyncapi.yaml` (AsyncAPI 2.6) — derived strictly from
  `process/{capability-id}/bus.yaml` + `schemas/BNK.RLVR.RVT.*.schema.json` +
  `kpack`'s `.slices.emitted_events[] | select(.layer=="resource")` / `.slices.consumed_events[] | select(.layer=="resource")`.
- `lineage.json` — top-level lineage (capability + bcm + process metadata).
- `harness-report.md` — closure verdict.

Both specs carry a top-level `x-lineage` block plus per-operation,
per-message, per-channel `x-lineage` extensions so every entry traces back
to its `process/` source AND its `kpack` source. The harness also adds a
`*.Contracts.Harness/` project to the .NET solution (which re-runs the
validation on every `dotnet build`) and mounts `/openapi.yaml` and
`/asyncapi.yaml` endpoints in the Presentation project.

Invoke:

```
Skill: harness-backend
Args:  CAPABILITY_ID = <from task>
       (worktree is auto-detected from current branch)
```

Say:
> "Running harness-backend for TASK-[NNN] — generating openapi.yaml + asyncapi.yaml with full process / bcm lineage..."

If `/harness-backend` reports a closure failure (dangling
`x-lineage.process.*`, missing controller, BCM warning), surface the report
to the user and **do NOT proceed to Step 3**. The remediation depends on the
gap:

| Gap                                            | Resolution                                                  |
|------------------------------------------------|-------------------------------------------------------------|
| Dangling `x-lineage.process.*` reference       | run `/process <CAPABILITY_ID>` to amend the model           |
| Dangling `x-lineage.bcm.*` reference           | fix BCM upstream in `reliever-knowledge`                     |
| Missing controller / consumer in microservice  | feed the gap into the remediation loop (Step 3)             |
| Drift between generated and committed specs    | re-run the harness in default mode and commit the diff      |

Only the third row is a remediation-loop case — the others require an
upstream fix. Treat the first two as a **stall** (do not consume loop
budget): record `stalled_reason: "harness closure failed: <gap>"` and stop.

Once `/harness-backend` returns green, proceed to Step 3.

---

## Step 3 — Validate with the matching test skill (zone-aware)

After all implementation agents complete, invoke the test skill that matches
the capability zone:

| Zone | Test skill | Test agent | Targets |
|------|-----------|-----------|---------|
| Non-CHANNEL (BUSINESS_SERVICE_PRODUCTION, SUPPORT, REFERENTIAL, EXCHANGE_B2B, DATA_ANALYTICS, STEERING) | `/test-business-capability` | `test-business-capability` | .NET microservice under `sources/{cap-name}/backend/` |
| CHANNEL | `/test-app` | `test-app` | Frontend under `sources/{CAP_ID}/frontend/` and BFF under `sources/{CAP_ID}/bff/` |

The test skill spawns its agent (senior test engineer) to validate that the
delivered artifacts satisfy the Definition of Done, FUNC ADR rules, and the
product/strategic vision.

Pass to the test skill:
- The task identifier (`TASK-NNN`)
- The capability ID and zone
- Any port or path information printed by the implementation skills (the
  deterministic `COMPONENT_PORT` per the Deployment contract in CLAUDE.md —
  kind=`api` for backend, kind=`bff` for CHANNEL BFF, kind=`frontend` for
  the frontend; same formula `20000 + sha256("{capability_id}:{kind}") % 9000`)

Say (non-CHANNEL):
> "Running test-business-capability for TASK-[NNN] (loop [loop_count+1]/[max_loops])..."

Say (CHANNEL):
> "Running test-app for TASK-[NNN] (loop [loop_count+1]/[max_loops])..."

### If all tests pass

Proceed directly to Step 4 (close and open PR).

### If tests fail — Remediation loop

**Before each remediation iteration**, check the loop budget:

```
IF loop_count >= max_loops → trigger the Stall Procedure (see below)
ELSE:
  loop_count += 1
  Write updated loop_count to task file frontmatter
  Proceed with the remediation iteration
```

For each remediation iteration within budget:

1. **Identify the failing artifact** (BFF, frontend, microservice).

2. **Re-invoke the relevant implementation skill** with an additional remediation context
   block prepended to the prompt:

   ```
   ── REMEDIATION CONTEXT (loop [loop_count]/[max_loops]) ──
   The previous implementation of TASK-[NNN] failed the following test criteria:

   ❌ [Criterion 1]: [what the test found vs. what was expected]
      Suggested correction: [from the test skill's output]

   ❌ [Criterion 2]: [...]
      Suggested correction: [...]

   Re-implement only what is needed to fix these criteria. Do not touch passing code.
   ── END REMEDIATION CONTEXT ──
   ```

3. **After the fix is applied**, re-invoke the matching test skill (`/test-business-capability` for non-CHANNEL or `/test-app` for CHANNEL) for the same task — it will spawn a fresh test agent run.

4. **Repeat** from the budget check until all criteria pass or the budget is exhausted.

---

### Stall Procedure (loop budget exhausted)

Triggered when `loop_count >= max_loops` and tests still fail.

1. **Update the task file frontmatter**:
   ```yaml
   status: stalled
   loop_count: [current value]
   max_loops: [current value]
   stalled_reason: |
     Loop budget exhausted after [loop_count] iteration(s).
     Failing criteria at last run:
     - ❌ [Criterion 1]: [failure description]
     - ❌ [Criterion 2]: [failure description]
     Last test run: [DATE]
   ```

2. **Refresh `/tasks/BOARD.md`** by invoking `/sort-task` so the board reflects the `stalled` status immediately.

3. **Report to the user** — this is a **mandatory human checkpoint**:
   ```
   ⚫ TASK-[NNN] stalled after [loop_count] remediation loop(s).

   Loop budget: [loop_count]/[max_loops] used.

   Failing criteria at last run:
     ❌ [Criterion 1]: [failure description]
     ❌ [Criterion 2]: [failure description]

   The kanban board has been updated (status: stalled).
   No further automated remediation will be attempted.

   To resume work:
     /continue-work TASK-[NNN]            ← resets to [max_loops] loops
     /continue-work TASK-[NNN] --max-loops 20  ← resets with a custom budget

   You may also add guidance before relaunching:
     "The consent gate ID changed — look for #gate-consentement not #consent-gate"
   ```

4. **Stop** — do not proceed to Step 4. The task remains `stalled` until
   `/continue-work` is invoked.

---

## Step 4 — Track, Close, and Open PR

After all tests pass (or after the remediation loop concludes):

1. **Update the task status** in the task file:
   - Change `status: in_progress` (or `status: todo` if invoked directly) to `status: in_review`.
   - Add the PR URL as a new frontmatter field `pr_url:` so `/sort-task` can display it.
   - If the remediation loop ended with remaining failures, add `draft: true`.

   Example resulting frontmatter:
   ```yaml
   status: in_review
   pr_url: https://github.com/org/repo/pull/42
   ```

2. **Run validation** to confirm the implementation is coherent with the BCM:
   ```bash
   python tools/validate_repo.py
   python tools/validate_events.py
   ```

3. **(Removed)** No per-capability task index file is maintained — `/tasks/`
   contains only `BOARD.md` (refreshed automatically by `/sort-task`) and the
   `<CAP_ID>/TASK-*.md` cards. The TASK file's frontmatter status update
   in step 1 is sufficient — the board picks it up.

4. **Commit all changes** using the Conventional Commits format:
   ```bash
   git add <all relevant files — never git add -A>
   git commit -m "feat(TASK-NNN): <imperative subject ≤72 chars>

   <2–3 sentences: what was built and why, referencing the FUNC ADR>

   Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
   ```

5. **Push the branch** and open a PR:

   The component's `COMPONENT_PORT` is **deterministic** from `capability_id` +
   kind (api/bff/frontend) per the Deployment contract in CLAUDE.md — recompute
   it here rather than relying on the agent's stdout, so the PR body always
   matches the `.env`:

   ```bash
   CAP_ID="$(grep -E '^capability_id:' tasks/*/TASK-NNN-*.md | head -1 | awk '{print $2}')"
   KIND="api"   # bff for CHANNEL BFF, frontend for CHANNEL frontend
   COMPONENT_PORT=$(python3 -c "import hashlib; print(20000 + int(hashlib.sha256(f'$CAP_ID:$KIND'.encode()).hexdigest()[:8],16) % 9000)")
   ```

   There are **no infrastructure ports to derive** — RabbitMQ and the per-L2
   database live on the out-of-scope platform (or the optional
   `deployment/local/platform.compose.yml` stand-in), reachable by service
   name on the shared external Docker network `reliever-platform`.

   Build the PR body using this template, substituting all placeholders:

   ```bash
   git push -u origin "$BRANCH_NAME"

   gh pr create \
     --title "feat(TASK-NNN): <subject line>" \
     --base main \
     --body "$(cat <<'PRBODY'
   ## Implemented Capability

   **[Capability Name]** ([Capability ID]) — Zone [TOGAF zone]
   Epic [N] — [Epic name]

   ## What Was Built

   - [DoD criterion 1] ✅
   - [DoD criterion 2] ✅
   - [DoD criterion 3] ✅

   ## Test Results

   All Definition of Done criteria validated by `test-business-capability` (non-CHANNEL) or `test-app` (CHANNEL).
   Report: `tests/{capability-id}/TASK-NNN-{slug}/report.html`

   ## Local Test Environment

   > Each component ships its own `deployment/local/` (Dockerfile + compose +
   > `.env`). The compose runs **only the component image** and joins the
   > shared external Docker network `reliever-platform`; RabbitMQ + the per-L2
   > database live on the out-of-scope platform (use
   > `deployment/local/platform.compose.yml` as a stand-in if the real platform
   > is not installed).

   ### One-time prerequisite (any component)

   \`\`\`bash
   # Either the real platform is up, or the stand-in:
   docker compose -f sources/{CAP_ID}/{component}/deployment/local/platform.compose.yml up -d
   \`\`\`

   ### Backend (.NET or Python microservice) — non-CHANNEL only

   \`\`\`bash
   docker compose -f sources/{CAP_ID}/backend/deployment/local/docker-compose.yml up -d
   \`\`\`

   | Service | Local URL |
   |---------|-----------|
   | REST API | http://localhost:{COMPONENT_PORT} |
   | Health  | http://localhost:{COMPONENT_PORT}/health |
   | Swagger / OpenAPI | http://localhost:{COMPONENT_PORT}/swagger (or /docs) |

   > ⚠ For .NET only: `GITHUB_USERNAME` + `GITHUB_TOKEN` must be exported (NuGet
   > GitHub Packages feed). Used only at image build time.

   ### BFF (.NET Minimal API) — CHANNEL zone

   \`\`\`bash
   docker compose -f sources/{CAP_ID}/bff/deployment/local/docker-compose.yml up -d
   \`\`\`

   | Service | Local URL |
   |---------|-----------|
   | BFF REST | http://localhost:{COMPONENT_PORT_BFF} |
   | Health  | http://localhost:{COMPONENT_PORT_BFF}/health |

   ### Frontend (vanilla HTML/CSS/JS, nginx image) — CHANNEL zone

   \`\`\`bash
   docker compose -f sources/{CAP_ID}/frontend/deployment/local/docker-compose.yml up -d
   \`\`\`

   | Scenario | URL |
   |----------|-----|
   | Nominal | http://localhost:{COMPONENT_PORT_FRONTEND}?beneficiaireId=BEN-001 |
   | Consent refusal | http://localhost:{COMPONENT_PORT_FRONTEND}?beneficiaireId=BEN-001&consentement=refuse |

   ## Dev Environment Artifacts

   Each component also ships `deployment/dev/k8s/` (kustomize) and
   `deployment/dev/terraform/` (banking-tech modules only), derived via
   `kpack` in two contexts (`BNK.RLVR` → `BNK.TECH`) per the Deployment contract in CLAUDE.md.

   - Resolved platform capabilities: see `deployment/dev/terraform/README.md`.
   - Escape-hatch issues (when a needed banking-tech module is missing): {none |
     <list of `gh` issue URLs>}.

   ## Manual Test Plan

   - [ ] Platform stand-in (or real platform) is up: `docker ps` shows
         `rabbitmq` and the DB on the `reliever-platform` network.
   - [ ] `docker compose -f deployment/local/docker-compose.yml up -d` without errors
   - [ ] Service starts and binds the deterministic `COMPONENT_PORT`
   - [ ] `GET /health` returns 200
   - [ ] Nominal capability scenario works end-to-end
   - [ ] Business event visible in RabbitMQ Management (if applicable)
   - [ ] Frontend loads and displays stub data correctly (if applicable)
   - [ ] `kubectl apply -k deployment/dev/k8s/overlay/dev/ --dry-run=client` is clean
   - [ ] `terraform -chdir=deployment/dev/terraform init && terraform plan` is clean
         (or the README records the open banking-tech issue blocking it)

   ---
   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   PRBODY
   )"
   ```

   If `gh` is not available or the repository has no GitHub remote, skip the PR creation,
   commit locally, and tell the user:
   > "Changes committed on branch `feat/TASK-NNN-{slug}`. No GitHub remote detected — open a PR manually when ready."

6. **Report to the user:**
   > "TASK-[NNN] is complete. Branch `feat/TASK-NNN-{slug}` pushed. PR opened: [PR URL]
   >
   > Test results: [N]/[Total] DoD criteria validated ✅
   >
   > Deployment artifacts emitted under `sources/{CAP_ID}/{component}/deployment/`:
   > - local: Dockerfile + docker-compose.yml + .env (COMPONENT_PORT=[port])
   > - dev:   k8s/ (kustomize) + terraform/ (banking-tech modules)
   > - Banking-tech issues opened (if any): [list or 'none']
   >
   > Local test environment (requires the platform or `platform.compose.yml` stand-in):
   > - Backend / BFF: http://localhost:[COMPONENT_PORT]/health
   > - Frontend: http://localhost:[COMPONENT_PORT_FRONTEND]?beneficiaireId=BEN-001 (if generated)
   >
   > Next available tasks for this capability:
   > - TASK-[NNN+1]: [title] (previously blocked on this task)
   >
   > Other ready tasks in the pipeline:
   > - [TASK-NNN from other capabilities, if any]"

---

## Important Boundaries

- **This skill does not write application code directly** — it delegates to the
  `implement-capability`, `implement-capability-python`, `create-bff`,
  and `code-web-frontend` agents.
- **This skill does not re-open design decisions** — the task file is the source of truth.
  If something in the task is wrong, the fix is to update the task file (via the task skill)
  before running code.
- **One task at a time** — do not batch multiple tasks in one invocation. Each TASK-NNN
  is an independent unit of work.
- **Zone detection is mandatory** — never spawn `implement-capability*`
  for a CHANNEL task, and never spawn `create-bff` or `code-web-frontend`
  for a non-CHANNEL task.
- **Language detection is mandatory for Path A & Path C** — the
  `implement-capability*` agent variant is selected from the TECH-TACT
  ADR `tags` (step 6c). Never pick the agent from the capability id
  prefix or the zone alone.
- **Tests are not optional** — the matching test agent (test-business-capability for non-CHANNEL, test-app for CHANNEL) always runs after implementation.
  The only exception is when Playwright cannot be installed (fallback to manual checklist).
