---
name: task
description: >
  Generates concrete implementation tasks for a planned business capability, ready to be 
  executed by the implement-capability agent. Tasks are written to /tasks/{capability-id}/TASK-NNN-*.md. 
  Use this skill whenever the user wants to generate tasks from a roadmap, break epics into 
  implementation work, create the task list for a capability, or prepare work for coding. 
  Trigger on: "generate tasks", "create tasks", "break down the roadmap", "tasks for capability", 
  "implementation tasks", "what are the tasks", or any time a roadmap.md exists for a capability 
  and the user is ready to define the implementation work items. Also trigger proactively 
  after a roadmap.md is created or updated for a capability.
---

# Task Skill

You are generating **implementation task files** for a business capability, based on its roadmap
and its Process Modelling layer. Each task will be picked up by the implement-capability
agent for execution. Tasks must contain enough context for a developer (or the
implement-capability agent) to work independently — without needing to ask questions.

---

## Sentinel — acquire before writing TASK cards

A PreToolUse hook (`tasks-folder-guard.py`) rejects every Write/Edit/MultiEdit/
NotebookEdit call targeting `tasks/<CAP>/TASK-*.md` unless the shared
task-pipeline sentinel `/tmp/.claude-task-pipeline.active` is present and
≤30 min old. This skill is on the allowlist (together with `/task-refinement`,
`/launch-task`, `/code`, `/fix`, `/continue-work`, and `/pr-merge-watcher`).
The agents these skills spawn (`implement-capability`, `create-bff`,
`code-web-frontend`, `test-business-capability`, `test-app`,
`harness-backend`) never touch TASK cards directly — they return verdicts
that the orchestrating skill applies.

Before the first TASK-card write:

```bash
touch /tmp/.claude-task-pipeline.active
```

At the very end (success or graceful abort):

```bash
rm -f /tmp/.claude-task-pipeline.active
```

If the work spans more than ~25 minutes between TASK-card writes (e.g. a
long sub-agent invocation), re-`touch` the sentinel just before the next
write to refresh its freshness window. A stale sentinel grants write
access to the next agent — explicit `rm -f` on exit is preferred.

---

## Process model — consumed read-only via `rlv-knowledge process`

> The DDD process model (aggregates, commands, policies, read-models, bus
> topology, JSON Schemas) is authored by the `/process` skill in the
> **reliever-knowledge** repo and consumed here **read-only** via
> `rlv-knowledge process <CAP_ID>` — exactly like the BCM corpus via `rlv-knowledge pack`.
> It does not live in this repo, so there is nothing to guard locally and
> nothing to write under `process/`.

This skill consumes the model as a primary input — tasks routinely reference
`AGG.*`, `CMD.*`, `POL.*`, `PRJ.*`, `QRY.*` identifiers from it. Fetch it once
via `rlv-knowledge process <CAPABILITY_ID>` and read the returned slices.

If the model evolves (new aggregate, renamed command, new policy), run
`/process <CAPABILITY_ID>` in the reliever-knowledge repo and merge its PR to
refresh the model, then re-run `/task`.

---

## Readiness gate — the process model must resolve via `rlv-knowledge process`

Before reading anything from the process model, verify it resolves. A model is
ready iff `rlv-knowledge process <CAP_ID>` returns exit 0 (rlv-knowledge resolves the
published `main` of reliever-knowledge by default).

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
CAP_ID="<CAPABILITY_ID>"

# The process model lives in reliever-knowledge now; it is ready iff rlv-knowledge
# can resolve it (rlv-knowledge resolves the published main by default).
if ! rlv-knowledge process "$CAP_ID" --compact >/tmp/process-model.json 2>/tmp/process-model.err; then
  echo "GATE-FAIL: no process model for $CAP_ID."
  echo "Run /process $CAP_ID in the reliever-knowledge repo and merge its PR, then retry."
  cat /tmp/process-model.err
  exit 1
fi
```

If the gate fails, **stop and surface the failure to the user with the redirect
message** — do not proceed to generate tasks. Once `/process <CAP_ID>` is run in
the reliever-knowledge repo and its PR merged, re-run `/task`.

---

## Before You Begin

1. **Identify the capability** to generate tasks for. Ask if not specified, or list plannable 
   capabilities (those with a `roadmap.md` under `/roadmap/{cap}/` but no `/tasks/{cap}/`
   directory yet, or with a stale task set). To enumerate plannable capabilities, run
   `rlv-knowledge list --level L2` (and `--level L3` if relevant) — never read `/bcm/*.yaml` directly.

2. **Fetch the capability pack** from the `rlv-knowledge` CLI — this is the **only** sanctioned 
   knowledge source. Do not read `/bcm/`, `/func-adr/`, `/adr/`, `/strategic-vision/`, or 
   `/product-vision/` directly; those paths are not authoritative in this checkout.

   ```bash
   rlv-knowledge pack <CAPABILITY_ID> --compact > /tmp/pack-task.json
   ```

   `<CAPABILITY_ID>` is the **full source-context-prefixed ID** (e.g.
   `BNK.RLVR.CAP.BSP.001.SCO`); the v2.0.0 CLI rejects the short `CAP.…` form
   with exit code 2.

   **Carry the knowledge-base ref into every TASK.** Read the
   `rlv-knowledge process <CAPABILITY_ID> --compact` envelope's `.knowledge_base.ref`
   (the model's git provenance) and copy it into each TASK's `bcm_ref`
   frontmatter field. This pins every task to the exact knowledge version it was
   derived from, so `/implementation-pipeline` and `/fix` can later
   `rlv-knowledge diff <bcm_ref> --capability <CAP_ID>` to detect upstream drift. If
   `.knowledge_base.ref` is absent, fall back to the current `rlv-knowledge version
   --compact` `ref` and note it as an assumption.

   Lightweight mode is enough for task generation — you do not need the rationale ADRs 
   behind the vision narratives. Read these slices selectively:

   | Slice                       | Used for                                              |
   |-----------------------------|-------------------------------------------------------|
   | `capability_self`           | task `capability_id`, `capability_name`, level, ADRs  |
   | `capability_definition`     | governing FUNC ADR(s) — decisions and constraints     |
   | `emitted_business_events`   | "Business Events to Produce" per task                 |
   | `consumed_business_events`  | "Event Subscriptions Required" per task               |
   | `carried_objects`           | "Business Objects Involved" per task                  |
   | `carried_concepts`          | terminology grounding — feeds Open Questions if fuzzy |
   | `governing_urba`            | URBA ADR constraints (event meta-model, naming…)      |

   Then read the local roadmap and the process model:
   - `/roadmap/{capability-id}/roadmap.md` — the source of epics and exit conditions (local)
   - the Process Modelling layer via `rlv-knowledge process <CAPABILITY_ID> --compact`
     (read-only). Tasks must reference the `AGG.*` / `CMD.*` / `POL.*` / `PRJ.*`
     / `QRY.*` identifiers from `.model.aggregates`, `.model.commands`,
     `.model.policies`, and `.model["read-models"]`, and the routing keys /
     subscriptions from `.model.bus` (use `.parsed`, falling back to `.raw` when
     null — `commands`/`read-models` are frequently `parsed:null`). If
     `rlv-knowledge process` does not resolve, stop and run `/process
     <CAPABILITY_ID>` in the reliever-knowledge repo and merge its PR first.
   - Existing tasks in `/tasks/{capability-id}/` — to avoid duplication (local)

   Check `pack.warnings` — non-empty entries should land in the `Open Questions` of the 
   first task that touches the affected area.

3. **Check the implement-capability agent** at `.claude/agents/implement-capability.md` 
   to understand what input format it expects, so tasks are written in a compatible structure.

---

## Hard rule — TASK-001 is ALWAYS the contract & stub task

Every capability, regardless of zone or roadmap shape, gets a mandatory
**TASK-001 = contract and development stub**. It is the first task to do
for any business capability, and the entry point for downstream consumers
that need *cold data* (canned events, canned query responses) before the
real implementation lands.

Rationale:
- Per `ADR-BCM-URBA-0009`, each capability owns the contract of every
  event it emits and every API surface it exposes. The stub is the
  earliest runnable embodiment of that contract.
- Consumers (other L2/L3 capabilities, BFFs, frontends) can subscribe to
  the bus AND call the HTTP API immediately, developing against canned
  data while the real domain logic is built in parallel.
- The stub never blocks the real implementation: TASK-002+ run in
  parallel and replace the stub piece by piece. The stub is
  decommissioned (or kept inert via `STUB_ACTIVE=false`) once the real
  implementation reaches feature parity for the surface in question.

> Throughout this section, `process/<CAP_ID>/bus.yaml`, `.../api.yaml` and
> `.../schemas/` name the **logical** model artifacts — they are fetched via
> `rlv-knowledge process <CAP_ID>` (`.model.bus`/`.model.api`, using `.parsed` or the
> `.raw` fallback, and `.schemas[...]`), not read from a local `process/` folder
> (there is none in this repo).

Properties of TASK-001:

| Property | Value |
|---|---|
| `task_id` | `TASK-001` (always) |
| `task_type` | `contract-stub` (always) |
| `depends_on` | `[]` (always — self-founding) |
| Surface covered | **Events + Query API** — every `RVT.*` listed in `process/<CAP_ID>/bus.yaml` (publish side) AND every HTTP operation listed in `process/<CAP_ID>/api.yaml` (query side) |
| Output location | `sources/<CAP_ID>/stub/` (single .NET worker that both publishes RVT events on RabbitMQ AND serves the HTTP query surface with canned data) |
| Schemas | Read-only from `process/<CAP_ID>/schemas/` — the stub validates outgoing payloads against them; it does **not** author them |
| Decommissioning | DoD includes an explicit decommission bullet — the stub is retired or toggled off when the real implementation reaches feature parity |

Subsequent tasks (TASK-002+) are the real-implementation epics from the
roadmap. They do **not** declare `depends_on: [TASK-001]` — the stub is a
parallel consumer-facing safety net, not a prerequisite. Real tasks may
still declare dependencies on each other (and on tasks in upstream
capabilities).

If `process/<CAP_ID>/api.yaml` is empty (no query surface) the stub still
ships, but only the event-publishing half is materialised. If
`process/<CAP_ID>/bus.yaml` declares no emitted events (consumer-only
capability) the stub serves only the HTTP query surface. If both are
empty, stop and surface a gap — there is nothing to stub.

---

## Task Structure

Each task is a markdown file in `/tasks/{capability-id}/TASK-NNN-short-slug.md`
(flat per-capability folder — no nested `tasks/` subdirectory).

Tasks are grouped by epic. Number them sequentially across the capability:
**TASK-001 is reserved for the mandatory contract-and-stub task** (see the
hard rule above); the first real-implementation task starts at TASK-002.

### What makes a good task?

A good task:
- Is **self-contained**: a developer reading only this file knows what to build
- Has a clear **Definition of Done** (not "implement X" but "when X is complete, Y is verifiable")
- Cites the **business capability** and **ADR** it implements
- Names the **business events** to produce (by name, as in the BCM)
- Specifies the **business objects** involved
- Lists its **dependencies** on other tasks (by TASK-NNN ID)
- Does not specify implementation technology (that's the implement-capability agent's job)

### Task file format

```markdown
---
task_id: TASK-[NNN]
capability_id: BNK.RLVR.CAP.[ZONE].[NNN].[CODE]   # full source-context-prefixed ID
capability_name: [Name]
epic: [Epic N — Epic Name]
status: todo
priority: high | medium | low
depends_on: [TASK-NNN, TASK-NNN]  # empty list if none
task_type: full-microservice      # OR: contract-stub (TASK-001 only — see hard rule above)
bcm_ref: [v2.0.0]                 # knowledge-base ref the model was built from — see below
---

# TASK-[NNN] — [Short descriptive title]

## Context
[2-3 sentences: why this task exists, what business capability it contributes to, 
which service offer it serves]

## Capability Reference
- Capability: [Name] ([ID])
- Zone: [TOGAF zone]
- Governing ADR(s): [ADR-BCM-FUNC-NNNN]

## What to Build
[Clear description of the business behavior to implement. No technology — what the 
capability must be able to do when this task is done]

## Business Events to Produce
- [EventName] — emitted when [condition]
- [EventName] — emitted when [condition]

## Business Objects Involved
- [BusinessObjectName] — [role in this task]

## Event Subscriptions Required
- [EventName] (from [CapabilityID]) — consumed to [reason]

## Definition of Done
- [ ] [Verifiable condition 1]
- [ ] [Verifiable condition 2]
- [ ] All business events listed above are emitted under the correct conditions
- [ ] validate_repo.py passes with no errors
- [ ] validate_events.py passes with no errors

## Acceptance Criteria (Business)
[Business-language description of what a business owner would verify to accept this task]

## Dependencies
- [TASK-NNN]: [Why this must be done first]
- [BNK.RLVR.CAP.ZONE.NNN]: [External capability dependency]

## Open Questions
- [ ] [Any unresolved question that must be answered before starting]
```

> **Important — Open Questions format:** every entry in `## Open Questions` MUST be written as a Markdown checkbox `- [ ]`. The `/sort-task` skill detects unresolved questions by counting unchecked checkboxes in this section. A plain bullet `-` will NOT be detected and the task will be wrongly classified as `ready`. When a question is resolved, tick it (`- [x]`) instead of deleting it, to preserve the audit trail.

### TASK-001 stub template

This template is what TASK-001 should look like for every capability.
Adapt the surface lists (`RVT.*` events, HTTP operations) to what the process
model's `bus` and `api` slices actually declare (the logical `process/<CAP_ID>/`
artifact names below are stable provenance references, read via `rlv-knowledge
process <CAP_ID>` — `.model.bus` and `.model.api`). The stub may need to serve
only events, only queries, or both — shape the DoD accordingly.

```markdown
---
task_id: TASK-001
capability_id: BNK.RLVR.CAP.[ZONE].[NNN].[CODE]   # full source-context-prefixed ID
capability_name: [Name]
epic: Epic 0 — Contract and Development Stub
status: todo
priority: high
depends_on: []
task_type: contract-stub
bcm_ref: [v2.0.0]                 # from `rlv-knowledge process <CAP_ID> --compact` .knowledge_base.ref
---

# TASK-001 — Contract and development stub for [Capability Name]

## Context
`BNK.RLVR.CAP.[ZONE].[NNN].[CODE]` exposes [N] resource events on the operational
bus and [M] HTTP operations on its query surface. Per `ADR-BCM-URBA-0009`
this capability owns the contract of both. As long as the real
implementation is not in place, this stub publishes the contracted events
with simulated values AND serves the query surface with canned cold data,
so any downstream consumer (BFFs, frontends, other capabilities) can
develop in complete isolation.

The bus topology (RabbitMQ topic exchange owned by this capability,
routing key `{BusinessEventName}.{ResourceEventName}`, payload form
= domain event DDD) is fixed by `ADR-TECH-STRAT-001`. The HTTP surface
follows `ADR-TECH-STRAT-003`.

## Capability Reference
- Capability: [Name] (BNK.RLVR.CAP.[ZONE].[NNN].[CODE])
- Zone: [TOGAF zone]
- Governing FUNC ADR(s): [ADR-BCM-FUNC-NNNN]
- Strategic-tech anchors: ADR-TECH-STRAT-001 (bus), ADR-TECH-STRAT-003 (API), ADR-TECH-STRAT-004 (referential / PII when applicable)

## What to Build
A runnable development stub under `sources/<CAP_ID>/stub/` that:

1. **Publishes resource events** for every `RVT.*` declared in
   `process/<CAP_ID>/bus.yaml` — on the capability's owned topic exchange,
   with the routing key convention from ADR-TECH-STRAT-001, at a
   configurable cadence (default 1–10 events/min). Payloads validate
   against `process/<CAP_ID>/schemas/RVT.*.schema.json`.
2. **Serves the query surface** for every operation declared in
   `process/<CAP_ID>/api.yaml` — returning canned cold data shaped to the
   declared response schema. Pre-seeded with at least 3 representative
   fixtures that consumers can reliably retrieve.
3. **Is activatable / deactivatable** via `STUB_ACTIVE=true|false`
   (inactive in production).
4. **Is self-validating** — every outgoing payload (event or HTTP
   response) is validated against the schema before emission.

## Events to Stub
- `RVT.[CAP].EVENT_NAME` — published at cadence X with simulated values from fixture set Y
- ...

## Query Operations to Stub
- `GET /[resource]` — returns canned list of N fixtures
- `GET /[resource]/{id}` — returns the matching fixture, or 404 for unknown IDs
- ...

## Business Objects Involved
- `OBJ.[CAP].[OBJECT]` — carried by the events / returned by the queries

## Required Event Subscriptions
None — the stub is a producer + query server, not a consumer.

## Definition of Done
- [ ] Stub source code under `sources/<CAP_ID>/stub/`
- [ ] For every `RVT.*` in `process/<CAP_ID>/bus.yaml`: stub publishes on the owned topic exchange with the ADR-TECH-STRAT-001 routing key; every payload validates against the corresponding `process/<CAP_ID>/schemas/RVT.*.schema.json`
- [ ] For every operation in `process/<CAP_ID>/api.yaml`: stub serves canned responses validating against the declared response schema
- [ ] At least 3 representative fixtures are pre-seeded and retrievable by stable IDs (so consumers can write deterministic integration tests against the stub)
- [ ] Cadence configurable in 1–10 events/min by default (override + justification needed outside this range)
- [ ] `STUB_ACTIVE` env var gates the stub (off in production)
- [ ] An automated self-validation check exists (CI unit test recommended) — independent of bus / HTTP availability
- [ ] **Decommissioning** — the stub is documented as retired (or permanently kept inert) once the real implementation (TASK-002+) reaches feature parity for the surface in question. A note in the stub's README states the criteria for decommissioning.

## Acceptance Criteria (Business)
A developer working on any consumer of this capability can, with only the
artifacts produced by this task: (a) subscribe a queue to the owned topic
exchange and receive validating event payloads, AND (b) call every HTTP
operation and receive validating canned responses. No dependency on the
real implementation. When the real implementation lands later, no
schema-driven or contract-driven consumer change is required.

## Dependencies
None. This task is self-founding for the capability.

## Open Questions
- [ ] [Any unresolved question — schemas missing, bus topology unclear, etc.]
```

---

## Step 1 — Review the Roadmap with the User

Before generating tasks, present the epic breakdown from the roadmap and ask:
> "I'll generate tasks for [capability]. TASK-001 will be the mandatory
> contract-and-stub task (consumer-facing cold data). The roadmap has [N]
> epics for the real implementation. Should I generate tasks for all
> epics, or start with a specific one?"

For each epic:
- Confirm the exit condition is clear enough to generate verifiable tasks
- Flag any epic where more information is needed before tasks can be written
- Identify which tasks are sequential within the epic vs. which can run in parallel

---

## Step 2 — Generate the mandatory TASK-001 stub

Always emit TASK-001 first, using the **TASK-001 stub template** above.
Populate it from the `rlv-knowledge process <CAP_ID> --compact` envelope:

- Enumerate every `RVT.*` declared in the bus slice (`.model.bus.parsed`,
  fallback `.raw`) — list them under "Events to Stub" with the routing key the
  bus topology mandates.
- Enumerate every operation declared in the api slice (`.model.api.parsed`,
  fallback `.raw`) — list them under "Query Operations to Stub" with their
  canned-response shape.
- Reference the JSON Schemas from `.schemas["<F>.schema.json"]` (read-only —
  the stub validates against them, never authors them).

The TASK-001 file lives in `tasks/<CAP_ID>/TASK-001-contract-and-stub-*.md`
(slug describes the capability surface, e.g.
`TASK-001-contract-and-stub-beneficiary-referential.md`).

If `rlv-knowledge process <CAP_ID>` does not resolve, **stop** and tell the user to
run `/process <CAP_ID>` in the reliever-knowledge repo and merge its PR first.

---

## Step 3 — Generate the real-implementation tasks (TASK-002+)

For each epic in the roadmap, generate the minimum set of tasks that together achieve the epic's exit condition. 
Avoid both:
- **Over-splitting**: don't create 10 micro-tasks where 3 coherent tasks suffice
- **Under-splitting**: don't create one task so large it requires multiple implement-capability 
  invocations with implicit coordination

A good rule of thumb: one task = one bounded context in the implement-capability sense. If the 
epic spans multiple bounded contexts, it should become multiple tasks.

Assign tasks:
- Sequential numbering starting at TASK-002 (TASK-001 is reserved for the stub)
- Do **not** add `depends_on: [TASK-001]` — real-implementation tasks
  run in parallel with the stub, not behind it. They may still declare
  dependencies on each other or on upstream capabilities.
- Epic grouping: all tasks within an epic get a comment block header in the tasks directory listing

---

## Step 4 — Write the Task Files

Write each task file to `/tasks/{capability-id}/TASK-NNN-[slug].md` — a flat
per-capability folder, no nested `tasks/` subdirectory. Create the
`/tasks/{capability-id}/` directory if it does not exist.

Do NOT write any other file under `/tasks/`. That folder holds only the
kanban: `BOARD.md` at its root (auto-generated by `/sort-task`) plus the
`<CAP_ID>/TASK-*.md` cards. Per-capability indices, summaries, roadmap
files, and contract folders all live elsewhere — see the layout rules in
the `/roadmap` (→ `/roadmap/`) skill. The process model is not a local lane
here; it is authored by `/process` in the reliever-knowledge repo and consumed
read-only via `rlv-knowledge process`.

After writing all tasks, tell the user:
> "Tasks for [capability] are committed to `/tasks/[capability-id]/`.
> TASK-001 is the mandatory contract-and-stub task — implement it first
> to unblock downstream consumers with cold data. TASK-002+ are the
> real-implementation tasks and can run in parallel with TASK-001.
> Use `/launch-task` (or `/launch-task auto`) to dequeue and the kanban
> view at `/tasks/BOARD.md` is refreshed automatically by `/sort-task`."
