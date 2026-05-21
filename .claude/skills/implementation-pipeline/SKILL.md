---
name: implementation-pipeline
description: >
  Orchestrates the local implementation pipeline: roadmap → task →
  sort-task / launch-task → code → test. Upstream knowledge (BCM YAML,
  FUNC/URBA/GOV/TECH ADRs, product/business/tech visions) is fetched on demand
  from the external `bcm-pack` CLI — this skill no longer drives any modeling
  or brainstorming session. The DDD tactical Process Modelling layer
  (aggregates, commands, policies, read-models, bus topology, JSON Schemas) is
  authored by `/process` in the external `banking-knowledge` repo and consumed
  here read-only via `bcm-pack process <CAP_ID>`; the local pipeline starts by
  consuming it, every downstream stage reading it as a read-only contract. The code stage is
  zone-aware AND language-aware: non-CHANNEL capabilities go to a
  language-matching implement-capability* agent — `implement-capability`
  (.NET 10 microservice) when the TECH-TACT ADR tags `dotnet` /
  `csharp` / `aspnet` (the default fallback), or `implement-capability-python`
  (FastAPI + motor / psycopg + aio-pika) when the TECH-TACT ADR tags
  `python` / `fastapi`. CHANNEL capabilities go to create-bff +
  code-web-frontend in parallel (language fixed: .NET BFF + vanilla JS
  frontend). The matching test agent then validates the result against the
  Definition of Done — test-business-capability (entry point:
  /test-business-capability) for non-CHANNEL backend microservices, test-app
  (entry point: /test-app) for CHANNEL frontend + BFF — with an automatic
  remediation loop bounded by a loop budget.
  The /sort-task skill keeps `/tasks/BOARD.md` fresh (read-only); /launch-task is
  the task scheduler — it tracks readiness, prioritizes by critical path, and
  spawns autonomous code agents in isolated worktrees.

  Use this skill to run the local pipeline, resume at any stage, check pipeline
  status, or coordinate process/roadmap/task generation across multiple
  capabilities. Spawns parallel subagents to run process / roadmap / task
  generation concurrently across capabilities.

  Trigger on: "run the pipeline", "where are we in the pipeline", "what's next",
  "resume the pipeline", "run all the roadmaps", "generate all tasks",
  "implementation pipeline", "full pipeline", or any time the user wants to
  advance through the local process-to-runtime journey.
---

# Implementation Pipeline Orchestrator

You are orchestrating the **local implementation pipeline** — a sequential flow
that takes a planned business capability all the way to a running, validated
artifact.

All upstream knowledge (BCM YAML, FUNC/URBA/GOV/TECH ADRs, product/business/tech
visions) lives in the external `banking-knowledge` repository and is exposed
read-only through the `bcm-pack` CLI. This skill never authors or modifies
upstream artifacts — it consumes them.

---

## The Pipeline

```
[0] Process                         (process skill — IN banking-knowledge, NOT this repo)   [PARALLELIZABLE per L2/L3 capability]
        ↓ reads:    `bcm-pack pack <CAP_ID> --deep` (BCM + FUNC/URBA/TECH-STRAT ADRs + visions)
        ↓ produces: the DDD tactical Process Modelling layer, authored upstream in
        ↓           banking-knowledge and consumed here read-only via `bcm-pack process <CAP_ID>`:
        ↓           ├─ .readme                     (framing + scenarios + open questions)
        ↓           ├─ .model.aggregates           (AGG.* — consistency boundaries, invariants)
        ↓           ├─ .model.commands             (CMD.* — verbs accepted, preconditions, errors)
        ↓           ├─ .model.policies             (POL.* — reactive event→command rules)
        ↓           ├─ .model["read-models"]       (PRJ.* + QRY.* — projections and queries)
        ↓           ├─ .model.bus                  (exchange + routing keys + subscriptions)
        ↓           ├─ .model.api                  (derived REST surface)
        ↓           └─ .schemas[...]               (JSON Schemas for CMD and RVT payloads)
        ↓ NOTE: `/process` runs in the banking-knowledge repo. The local pipeline does NOT
        ↓       author the process model — it consumes it via `bcm-pack process`. There is
        ↓       no process/ folder in this repo, so nothing to guard or write here.

[1] Roadmap                         (roadmap skill)                           [PARALLELIZABLE per L2 capability]
        ↓ reads:    `bcm-pack pack <CAP_ID> --deep` + `bcm-pack process <CAP_ID>` (read-only)
        ↓           + local `/roadmap/{capability-id}/roadmap.md` if updating an existing roadmap
        ↓ produces: /roadmap/{capability-id}/roadmap.md  (epics, milestones, exit conditions)
        ↓ NOTE: /tasks/ folder is reserved for the kanban (BOARD.md + <CAP_ID>/TASK-*.md) —
        ↓       the roadmap skill writes to /roadmap/, never to /tasks/.

[2] Task                            (task skill)                              [PARALLELIZABLE per capability]
        ↓ reads:    /roadmap/{capability-id}/roadmap.md (local) + `bcm-pack process <CAP_ID>` (read-only)
        ↓           + `bcm-pack pack <CAP_ID>` (BCM + ADRs)
        ↓ produces: /tasks/{capability-id}/TASK-NNN-*.md
                    (frontmatter: task_id, status, priority, depends_on, loop_count, max_loops)

[3a] Sort-task                      (sort-task skill)                         [READ-ONLY BOARD GENERATOR]
        ↓ reads:    all /tasks/**/TASK-*.md
        ↓ writes:   /tasks/BOARD.md  (auto-refreshed on every TASK file change via hook)
        ↓ computes: ready / blocked / needs_info / stalled / in_progress / in_review / done

[3b] Launch-task                    (launch-task skill)                       [SCHEDULER — drives stages 4-5]
        ↓ invokes:  /sort-task first to obtain a fresh report
        ↓ launches: code agents (manual, reactive on `ready` transition, or fully autonomous)
        ↓ enforces: idempotency (one code agent per task), one active task per capability

[4] Code                            (code skill)                              [PARALLELIZABLE per task — one agent per task]
        ↓ reads:    /tasks/{capability-id}/TASK-NNN.md
        ↓ creates:  isolated git worktree on branch feat/TASK-NNN-{slug}
        ↓ detects:  capability `zoning` → routes to the correct path
        ↓ Path A — non-CHANNEL: spawns the implement-capability agent
        ↓ Path B — CHANNEL:     invokes create-bff + code-web-frontend in parallel
        ↓ then:    invokes test-business-capability (non-CHANNEL) or test-app (CHANNEL) + remediation loop
        ↓ ends:    PR opened, status: in_review, loop_count tracked, stall on budget exhaust

[4a] implement-capability agent    (.NET 10 microservice, Clean Architecture + DDD)
         output: sources/{capability-name}/backend/
         allocates LOCAL_PORT (10000-59999) + MongoDB / RabbitMQ ports
         creates Domain / Application / Infrastructure / Presentation / Contracts projects
         writes /health endpoint for readiness probing
         reserves Contracts.Harness/ + contracts/specs/ for the harness step

[4a-bis] harness-backend agent     (contract harness — Path A only)
         entry point: /harness-backend
         input: the process model via `bcm-pack process <CAP_ID>` — logically
                 process/{cap}/{api.yaml,commands.yaml,read-models.yaml,
                 bus.yaml,schemas/} + bcm-pack pack <CAP_ID> --deep
         output: sources/{capability-name}/backend/
                   ├ src/{Namespace}.{CapabilityName}.Contracts.Harness/
                   └ contracts/specs/{openapi.yaml,asyncapi.yaml,
                                       lineage.json,harness-report.md}
         OpenAPI 3.1 — strict from process/api.yaml + commands + read-models +
                       schemas/CMD.* + bcm carried_objects
         AsyncAPI 2.6 — strict from process/bus.yaml + schemas/BNK.RLVR.RVT.* +
                        bcm emitted/consumed_resource_events
         every operation/channel/message carries x-lineage → process + bcm
         wires /openapi.yaml + /asyncapi.yaml endpoints on Presentation
         build target re-validates spec ↔ controllers ↔ consumers on every dotnet build
         skipped for Path B (CHANNEL — create-bff owns its surface) and Path C (contract-stub)

[4b] create-bff agent              (.NET 10 ASP.NET Core BFF — CHANNEL zone only)
         output: sources/{CAP_ID}/bff/
         allocates BFF_PORT + RabbitMQ ports, writes .env.local with branch slug
         per L3: dedicated endpoints, ETag/304, Cache-Control: no-store
         per consumed event: RabbitMQ consumer + state cache update
         OTel mandatory dimensions: capability_id, zone, deployable, environment={branch}

[4c] code-web-frontend agent       (vanilla HTML5/CSS3/JS — CHANNEL zone only)
         output: sources/{capability-id}/frontend/  (index.html, styles.css, api.js, app.js)
         follows frontend-baseline pattern; STUB_DATA in api.js is the test contract
         branch badge in header, dignity rule in DOM order, French vocabulary
         test injection points: ?beneficiaireId= and ?consentement=refuse

[5] Test (zone-aware)              (test-business-capability OR test-app agent)
        Path A — non-CHANNEL (entry: /test-business-capability)
          ↓ runs in:  ephemeral environment (.NET service + MongoDB + RabbitMQ via docker-compose)
          ↓ generates: tests/{cap-id}/TASK-NNN-{slug}/{conftest.py, test_dod.py,
                       test_business_rules.py, test_strategic.py, test_backend.py}
          ↓ asserts: REST endpoints, persistence, RabbitMQ event emission, OTel tags
        Path B — CHANNEL (entry: /test-app)
          ↓ runs in:  ephemeral environment (static HTTP server + BFF + RabbitMQ)
          ↓ generates: tests/{cap-id}/TASK-NNN-{slug}/{conftest.py, test_dod.py,
                       test_business_rules.py, test_strategic.py, test_bff.py?}
          ↓ modes:   full-mock | frontend+bff | bff-only
          ↓ asserts: DOM order (dignity rule), Playwright DoD checks, BFF /health + ETag/304
        ↓ reports: report.html + run.log; failures feed code's remediation loop
```

**Stages 0–2 can be fully parallelized** across capabilities (process modelling,
roadmap, task generation). **Stages 3–5 are driven by `/sort-task` (read-only
board) and `/launch-task` (orchestrator)** — this skill does not launch
implementation agents directly.

> **Read-only contract.** The process model is authored by `/process` in the
> **banking-knowledge** repo and is the **read-only input** of stages 1, 2, 4, 5
> and any `/fix` / `/continue-work` re-entry, fetched via `bcm-pack process
> <CAP_ID>` — exactly like the BCM corpus via `bcm-pack pack`. It does not live
> in this repo, so there is nothing to guard locally and nothing to write under
> `process/`. If a downstream stage discovers that the model is wrong, it must
> surface the gap and stop, so the user can re-run `/process <CAPABILITY_ID>` in
> the banking-knowledge repo and merge its PR.

---

## Step 1 — Assess Pipeline Status

The pipeline operates on a per-capability basis. For each capability the user
wants to advance, query `bcm-pack` to verify upstream knowledge is complete,
then check local artifacts. Do not `ls` `/bcm/`, `/func-adr/`, `/adr/`,
`/strategic-vision/`, `/product-vision/`, `/tech-vision/`, or `/tech-adr/` —
those paths are not authoritative locally and are typically absent.

```bash
# Pick a target capability (or iterate over `bcm-pack list --level L2`)
CAP_ID="BNK.RLVR.CAP.BSP.001"

# Upstream readiness — all required slices must be non-empty for stages 1-2 to run
bcm-pack pack $CAP_ID --deep --compact > /tmp/probe.json
jq '{
  product_vision:        (.slices.product_vision        | length),
  business_vision:       (.slices.business_vision       | length),
  tech_vision:           (.slices.tech_vision           | length),
  governing_tech_strat:  (.slices.governing_tech_strat  | length),
  capability_definition: (.slices.capability_definition | length),
  tactical_stack:        (.slices.tactical_stack        | length),
  capability_self:       (.slices.capability_self       | length),
  warnings:              .warnings
}' /tmp/probe.json

# Stage 0 — the process model (authored upstream in banking-knowledge), read via bcm-pack
bcm-pack process $CAP_ID --compact >/dev/null 2>&1 && echo "Stage 0: process model present" || echo "Stage 0: no process model"

# Local artifacts produced by this pipeline
ls /roadmap/$CAP_ID/roadmap.md                          # Stage 1
ls /tasks/$CAP_ID/TASK-*.md                        # Stage 2
ls /tasks/BOARD.md                                       # Stage 3 (sort-task / launch-task)
ls sources/*/{backend,stub,bff,frontend}/ 2>/dev/null  # Stage 4 artifacts
ls tests/*/TASK-*-*/report.html                         # Stage 5 reports

# Knowledge-base DRIFT — has upstream moved since this capability was modelled?
# The process model carries the ref it was built from in its .knowledge_base block.
PINNED_REF=$(bcm-pack process $CAP_ID --compact 2>/dev/null | jq -r '.knowledge_base.ref // empty')
CURRENT_REF=$(bcm-pack version --compact | jq -r '.ref')
if [ -n "$PINNED_REF" ] && [ "$PINNED_REF" != "$CURRENT_REF" ]; then
  bcm-pack diff "$PINNED_REF" --capability "$CAP_ID" --compact | jq '{from:.from.ref,to:.to.ref,empty:.empty,summary:.summary}'
fi
```

Report the status clearly:

```
Upstream (bcm-pack) for BNK.RLVR.CAP.BSP.001:
  ✅ product_vision / business_vision / tech_vision present
  ✅ FUNC ADR present (capability_definition non-empty)
  ✅ Tactical ADR present (tactical_stack non-empty)
  ✅ BCM YAML present (capability_self non-empty, no warnings)

Local pipeline:
  ✅ Stage 0 — Process: `bcm-pack process BNK.RLVR.CAP.BSP.001` resolves (aggregates, commands, policies, read-models, bus, api, schemas — authored upstream in banking-knowledge)
  ✅ Stage 1 — Roadmap: /roadmap/BNK.RLVR.CAP.BSP.001/roadmap.md
  ⏳ Stage 2 — Tasks: 3/8 epics covered
  ⬜ Stage 3 — Kanban: BOARD.md not yet generated
  ⬜ Stage 4 — No implementation artifacts
  ⬜ Stage 5 — No test reports

Knowledge drift:
  ⚠️  Process model pinned to v1.0.0; knowledge base now at v1.1.0 —
      `bcm-pack diff` reports 1 changed business event, 2 changed ADRs for this
      capability. Re-run `/process BNK.RLVR.CAP.BSP.001` to refresh the model,
      then re-derive roadmap/tasks, before resuming Stage 4.

Next action: complete task generation for the remaining 5 epics.
```

**Drift gate.** When `bcm-pack diff <pinned_ref> --capability <CAP_ID>` reports a
non-empty summary, the process model is stale relative to upstream knowledge.
Flag it loudly and recommend re-running `/process` in the banking-knowledge repo
(then `/roadmap` → `/task` here) before any further Stage 4 work — implementing
against a stale model silently breaks the traceability chain. An empty diff means
the artifact is current.

If any upstream slice is empty or `pack.warnings` is non-empty, the upstream
knowledge corpus is incomplete — direct the user to the upstream
`banking-knowledge` repository to fix it. This skill cannot author or modify
upstream artifacts.

---

## Step 2 — Guide or Execute the Next Action

### Stage 0 — Process Modelling (authored upstream in banking-knowledge)

Stage 0 is **not run from this repo.** The DDD Process Modelling layer is
authored by the `/process` skill in the **banking-knowledge** repo and consumed
here read-only via `bcm-pack process <CAP_ID>`. The local pipeline starts by
*consuming* that model, not producing it.

For each target capability, verify the model resolves:

```bash
CAP_ID="BNK.RLVR.CAP.ZONE.NNN"
if bcm-pack process "$CAP_ID" --compact >/dev/null 2>&1; then
  echo "✅ Stage 0 — process model for $CAP_ID resolves (proceed to Stage 1)"
else
  echo "⬜ Stage 0 — no process model for $CAP_ID."
  echo "   Run /process $CAP_ID in the banking-knowledge repo and merge its PR,"
  echo "   then resume the pipeline here."
fi
```

If the model does not resolve, direct the user to run `/process <CAP_ID>` in the
banking-knowledge repo and merge its PR — this skill cannot author it. Once it
resolves, the model is read-only input for every downstream stage; there is no
local `process/` folder and nothing to write here.

### Stage 1 — Roadmap generation (parallelizable per capability)

For each L2 capability without a `roadmap.md`, spawn one subagent:

```
Use the roadmap skill to generate a roadmap for capability [BNK.RLVR.CAP.ZONE.NNN — Name].

Knowledge access (mandatory):
- Source ALL BCM, ADR, and vision context from the `bcm-pack` CLI:
    `bcm-pack pack [BNK.RLVR.CAP.ZONE.NNN] --deep --compact`
  Do NOT read /bcm/, /func-adr/, /adr/, /strategic-vision/, /product-vision/,
  /tech-vision/, or /tech-adr/ directly. The pack returns slices for
  capability_self, capability_definition (FUNC ADR), tactical_stack
  (tactical ADR), governing_urba, governing_tech_strat, product_vision,
  business_vision, tech_vision — use these.

Local artifacts (read directly only if updating):
- /roadmap/[capability-id]/roadmap.md   (existing roadmap, if any)

Save the result to /roadmap/[capability-id]/roadmap.md
(Do NOT write to /tasks/ — that folder is reserved for the kanban.)
```

### Stage 2 — Task generation (parallelizable per capability)

For each capability with a roadmap but no tasks, spawn one subagent:

```
Use the task skill to generate tasks for capability [BNK.RLVR.CAP.ZONE.NNN — Name].
Read the roadmap from /roadmap/[capability-id]/roadmap.md (local).

Knowledge access (mandatory):
- Source ALL BCM and ADR context from the `bcm-pack` CLI:
    `bcm-pack pack [BNK.RLVR.CAP.ZONE.NNN] --compact`
  (lightweight is enough for task generation — the rationale ADRs are not
  needed). Do NOT read /bcm/, /func-adr/, /adr/, or /tech-adr/ directly.
  Use slices: capability_self, capability_definition,
  emitted_business_events, consumed_business_events, carried_objects,
  carried_concepts, governing_urba, tactical_stack.

Save tasks to /tasks/[capability-id]/TASK-*.md with frontmatter:
  task_id, capability_id, capability_name, epic, status, priority,
  depends_on, loop_count: 0, max_loops: 10
```

Launch all subagents in the same turn (parallel). Report progress as they
complete. After they finish, the `/sort-task` skill will detect the new TASK
files via the PostToolUse hook and refresh `/tasks/BOARD.md` automatically.

### Stage 3 — Hand off to the launch-task scheduler

Once tasks exist, **stop driving execution from this skill** — delegate to
`/launch-task` (with `/sort-task` as the read-only board view). Do not list
tasks here. Tell the user:

> "Tasks are ready. Use `/launch-task` to drive execution (or `/sort-task` for a
> read-only board view).
>
> `/launch-task` will:
> - Invoke `/sort-task` first to scan all `/tasks/**/TASK-*.md` and compute readiness
>   (todo / in_progress / in_review / done / blocked / needs_info / stalled).
> - Prioritize ready tasks by critical path × business priority.
> - Maintain `/tasks/BOARD.md` (auto-refreshed on every TASK file change via hook).
> - Launch one `code` agent per ready task — manually, reactively (when a dependency
>   merges), or fully autonomously (`/launch-task auto`).
> - In autonomous mode, each task gets its own git worktree under
>   `/tmp/kanban-worktrees/TASK-NNN-{slug}/` and a sub-agent that works in isolation.
> - Enforce strict idempotency: at most one `code` agent per task at a time.
> - Reflect status changes back to the board immediately.
>
> Special states:
> - 🟠 `needs_info` — open questions in the TASK file; resolve them or run
>   `/task-refinement TASK-NNN`.
> - ⚫ `stalled` — code skill exhausted its `max_loops` budget without passing tests;
>   resume with `/continue-work TASK-NNN [--max-loops N]`."

### Stage 4 — Code execution (driven by /launch-task or manual /code)

When `/launch-task` (or the user via `/code TASK-NNN`) launches a task, the code skill:

1. **Verifies prerequisites** — status is `todo`/`in_progress`, all `depends_on` are `done`,
   no open questions, status not `stalled`.
2. **Reads loop counters** — initializes `loop_count: 0`, `max_loops: 10` if absent.
3. **Detects the capability zone AND the implementation language.**
   Zone is read from the `bcm-pack` slice (`capability_self.zoning`).
   Language is read from `tactical_stack[0].tags` (the TECH-TACT ADR):
   `python` / `fastapi` route to `implement-capability-python`,
   `dotnet` / `csharp` / `aspnet` route to `implement-capability`, and
   a missing / silent tactical_stack falls back to `implement-capability`
   with a warning. Together they determine the implementation path:

   | `zoning`                     | Path | TECH-TACT `tags`            | Agent invoked                                 |
   |------------------------------|------|-----------------------------|-----------------------------------------------|
   | `BUSINESS_SERVICE_PRODUCTION`| A    | `python` / `fastapi`        | `implement-capability-python`                 |
   | `BUSINESS_SERVICE_PRODUCTION`| A    | `dotnet` / `csharp` / (none)| `implement-capability` (default)              |
   | `SUPPORT`                    | A    | `python` / `fastapi`        | `implement-capability-python`                 |
   | `SUPPORT`                    | A    | `dotnet` / `csharp` / (none)| `implement-capability` (default)              |
   | `REFERENTIAL`                | A    | (same language matrix as above)                                              |||
   | `EXCHANGE_B2B`               | A    | (same language matrix as above)                                              |||
   | `DATA_ANALYTICS`            | A    | (same language matrix as above)                                              |||
   | `STEERING`                   | A    | (same language matrix as above)                                              |||
   | `CHANNEL`                    | B    | n/a — language fixed         | `create-bff` + `code-web-frontend` (parallel) |

4. **Creates an isolation branch** `feat/TASK-NNN-{slug}` from `main` (or works in the
   pre-existing worktree under `/tmp/kanban-worktrees/`).
5. **Summarizes** what will be built and waits for the user to confirm (skipped in
   autonomous `/launch-task auto` mode).
6. **Invokes the implementation skill(s)**:

   - **Path A (non-CHANNEL)** — the language-matching `implement-capability*` agent
     scaffolds a complete microservice under `sources/{capability-name}/backend/`.
     `implement-capability` emits a .NET 10 solution (Domain / Application /
     Infrastructure / Presentation / Contracts projects, MongoDB, MassTransit on
     RabbitMQ). `implement-capability-python` emits an equivalent Python 3.12+
     hexagonal package (FastAPI + uvicorn, motor or psycopg, aio-pika, pydantic
     v2, structlog, OpenTelemetry Day 0). Both share the same decision framework
     and port-allocation conventions:
     - Allocates `LOCAL_PORT` from `shuf -i 10000-59999`; derives `MONGO_PORT = LOCAL_PORT+100`,
       `RABBIT_PORT = +200`, `RABBIT_MGMT_PORT = +201`.
     - Generates Domain / Application / Infrastructure / Presentation / Contracts projects
       wired into a `.sln`, with `nuget.config`, `docker-compose.yml`, MongoDB repository,
       command/read controllers, factory, DTO, and a `GET /health` endpoint required by
       the test-business-capability agent for readiness.
     - All bus channels and queues are scoped by `{branch}-{ns-kebab}-{cap-kebab}-channel`
       to prevent cross-branch contamination.

   - **Path B (CHANNEL)** — the `create-bff` agent (senior backend engineer, BFF
     specialist) and the `code-web-frontend` agent (senior frontend engineer,
     vanilla web specialist) run in **parallel**:
     - `create-bff` produces `sources/{CAP_ID}/bff/`: ASP.NET Core Minimal
       API, one endpoint file per L3, one consumer per consumed event, an in-memory state
       cache with ETag/`If-None-Match`/`Cache-Control: no-store`, OTel instrumentation
       carrying `capability_id`, `zone`, `deployable`, `environment={branch}`. Allocates
       `BFF_PORT` and writes `.env.local` (gitignored) so the test-app agent can
       discover the port.
     - `code-web-frontend` produces `sources/{capability-id}/frontend/`: vanilla HTML5 +
       CSS3 + JS following the `frontend-baseline` pattern. Branch badge in `<header>`,
       dignity rule expressed as DOM order, French business vocabulary, complete `STUB_DATA`
       in `api.js` (canonical test contract), and stable test selectors
       (`#section-progression`, `#consent-gate`, `#table-historique`, `[data-filtre]`,
       etc.). URL injection points: `?beneficiaireId=` and `?consentement=refuse`.

7. **Invokes the matching test skill** (Stage 5 — see below):
   - **Path A (non-CHANNEL)** — `/test-business-capability`, spawning the
     `test-business-capability` agent against the .NET microservice
     (`backend-only` mode).
   - **Path B (CHANNEL)** — `/test-app`, spawning the `test-app` agent against the
     frontend + BFF (mode auto-detected: `full-mock`, `frontend+bff`, or `bff-only`).

8. **Remediation loop** — if any test fails, the code skill increments `loop_count` and
   re-invokes the failing implementation skill with a `── REMEDIATION CONTEXT ──` block
   listing the criteria that failed and the suggested correction. Repeats until all tests
   pass **or** `loop_count >= max_loops`.

9. **Stall procedure** — if the loop budget is exhausted with failing tests:
   - Update task frontmatter: `status: stalled`, write `stalled_reason` (last failing
     criteria + date), keep `loop_count` and `max_loops`.
   - Invoke `/sort-task` to refresh `/tasks/BOARD.md` so the board reflects the ⚫ state.
   - Stop. Tell the user to run `/continue-work TASK-NNN [--max-loops N]` with optional
     guidance to relaunch.

10. **Closure** — when tests pass:
    - Set `status: in_review`, add `pr_url:` to the frontmatter.
    - Update the task index `index.md`.
    - Commit with Conventional Commits format (`feat(TASK-NNN): …`).
    - Push branch and `gh pr create` with a body that includes:
      DoD checklist, test report path, local stack instructions for backend / BFF /
      frontend with the correct ports (`LOCAL_PORT`, `MONGO_PORT`, `RABBIT_PORT`,
      `RABBIT_MGMT_PORT`, `BFF_PORT`), and the manual test plan.
    - Report next available tasks (newly unblocked).

### Stage 5 — Test (zone-aware, invoked by code; can be invoked manually)

Two distinct skills, picked by the `/code` skill from the capability zone:

**Path A — non-CHANNEL (`/test-business-capability`, agent: `test-business-capability`)**

Runs in a **temporary, isolated `/tmp/test-{cap-id}-XXXXXX` directory**:
1. Brings up MongoDB + RabbitMQ via the agent-generated `docker-compose.yml`,
   then starts the .NET microservice on its `LOCAL_PORT` and probes `/health`.
2. Generates `tests/{capability-id}/TASK-NNN-{slug}/`:
   - `conftest.py` — `requests.Session`, `pika.BlockingConnection` to RabbitMQ
     on `RABBIT_PORT`, `pymongo.MongoClient` on `MONGO_PORT`.
   - `test_dod.py` — one test per `[ ]` item in the task's "Definition of Done"
     (REST endpoint, persistence assertion, event emission).
   - `test_business_rules.py` — aggregate invariants and roadmap scoping rules.
   - `test_strategic.py` — vocabulary heuristics on event payloads / errors.
   - `test_backend.py` — `/health`, OTel `environment` tag, branch-scoped exchange
     existence in RabbitMQ.
3. Tears down the .NET process and `docker compose down -v` on exit.

**Path B — CHANNEL (`/test-app`, agent: `test-app`)**

Runs in a **temporary, isolated `/tmp/test-app-{cap-id}-XXXXXX` directory**:
1. Copies frontend artifacts (originals are never touched).
2. Picks a free HTTP port and launches `python -m http.server` for the static frontend.
3. If `sources/{CAP_ID}/bff/.env.local` exists, starts the BFF on its
   recorded `BFF_PORT` and waits up to 15s for `/health` to return 200.
4. Generates `tests/{capability-id}/TASK-NNN-{slug}/`:
   - `conftest.py` — Playwright fixtures, mocked routes derived from `STUB_DATA`,
     `?beneficiaireId=` and `?consentement=refuse` URL injection.
   - `test_dod.py` — one test per `[ ]` item in the task's "Definition of Done".
   - `test_business_rules.py` — derived from FUNC ADRs and roadmap scoping decisions
     (dignity rule order, V0-without-gamification, business-language errors).
   - `test_strategic.py` — alignment with the product vision (French labels, encouraging
     vocabulary).
   - `test_bff.py` (when a BFF is running) — `/health`, snapshot endpoints, ETag/304
     behavior, `environment` tag matches `{branch}`.

Both paths then:
5. Run `pytest -v --tb=short --html=…/report.html`.
6. Translate results into business language (✅/❌ per DoD criterion + per ADR rule),
   write `report.html` and `run.log`, then **kill all spawned processes and remove
   the temporary directory**. The originals are never modified.
7. If tests fail and the code skill called the test agent, the
   failure list feeds the code skill's remediation loop. If tests fail and the user
   invoked the skill directly, the report is the deliverable.

If Playwright cannot be installed, the skill falls back to a `manual-checklist.md`
under the same `tests/{capability-id}/TASK-NNN-{slug}/` directory.

---

## Pipeline Integrity Checks

| Stage | Prerequisite |
|-------|--------------|
| 0 (Process) | `bcm-pack pack <CAP_ID> --deep` returns non-empty `capability_self`, `capability_definition`, `tactical_stack`, `governing_urba`, `governing_tech_strat`, `product_vision`, `business_vision`, `tech_vision`, and `pack.warnings` is empty. The full upstream chain (product → strategic business → strategic tech → FUNC ADR → tactical ADR → BCM YAML) must be in place in the `banking-knowledge` repo. |
| 1 (Roadmap) | Stage 0 prerequisites + `bcm-pack process <CAP_ID>` resolves (exit 0) with at least `.readme`, `.model.aggregates`, `.model.commands`, `.model.policies`, `.model["read-models"]`, `.model.bus`. |
| 2 (Task) | Stage 1 prerequisite + local `/roadmap/{capability-id}/roadmap.md` has at least one epic with an exit condition |
| 3 (sort-task / launch-task) | At least one `TASK-NNN-*.md` in local `/tasks/*/` with valid frontmatter |
| 4 (Code) | Task status is `todo` (or `in_progress` re-entry); all `depends_on` are `done`; no open questions; not `stalled`; `bcm-pack process <CAP_ID>` resolves (task references AGG/CMD/POL/PRJ/QRY identifiers from the model) |
| 5 (Test) | An implementation artifact exists in `sources/{CAP_ID}/{backend,stub,bff,frontend}/` |

If a prerequisite is missing, explain which earlier stage must be completed
first. If the gap is upstream (any required `bcm-pack` slice is empty), point
the user to the `banking-knowledge` repository — this skill cannot fix it.

---

## Governance Reminders

- **All upstream context is read-only.** GOV / URBA / TECH-STRAT / FUNC /
  TACTICAL ADRs and BCM YAML live in the `banking-knowledge` repo and are
  consumed via `bcm-pack` only. To author or update them, work in that
  repository directly.
- Every task must trace back to a roadmap epic, which traces back to an L2
  capability whose `bcm-pack` slice is complete (capability_self,
  capability_definition, tactical_stack).
- Every implementation artifact (microservice, BFF, frontend) must be
  reachable from a TASK-NNN, which is itself reachable from a roadmap epic.

**The traceability chain is unbreakable:**

```
[upstream — banking-knowledge / bcm-pack]
  Service Offer → Strategic L1 → Strategic Tech (TECH-STRAT) → IS L1/L2 (FUNC) →
  Tactical Tech (TECH-TACT) → BCM YAML
                          ↓
[upstream — banking-knowledge / bcm-pack process]
  Process Modelling (consumed via `bcm-pack process`)
                          ↓
[local — this repo]
  Roadmap Epic → Task → Code → Tests → PR
```

Any stage that cannot establish this chain must stop and surface the gap to
the user.

**The process layer is authored upstream.** Only `/process` can author the
process model, and it does so in the **banking-knowledge** repo; this repo
consumes it read-only via `bcm-pack process <CAP_ID>`. There is no local
`process/` folder here, so branches and PRs opened by `/code`, `/fix`, or
`/launch-task` (and their CI/CD pipelines) carry no `process/` diff — there
is nothing to guard locally.

---

## Operational Notes

- **The `/sort-task` skill runs on every TASK file change** (via PostToolUse hook). It
  refreshes `/tasks/BOARD.md` automatically — do not regenerate it from this skill.
- **Branch / environment isolation is end-to-end.** Every implementation component
  (implement-capability agent, create-bff agent, code-web-frontend agent) reads the
  current git branch slug and embeds it in artefact names: bus channels, RabbitMQ
  exchanges/queues, OTel `environment` tag, frontend branch badge. The
  test-app agent reads `.env.local` to find the BFF port for the active
  branch. This guarantees that concurrent worktrees launched by `/launch-task auto` never
  collide on infrastructure.
- **Port allocation is per-component, not per-pipeline.** The implement-capability agent
  allocates `LOCAL_PORT` 10000–59999 + 100/200/201 offsets. The create-bff agent allocates
  `BFF_PORT` + 100/101 offsets. The PR body assembled by the code skill must include all relevant
  ports in the local-test instructions.
- **Loop counters live on the TASK file**, not on the board. The code skill is the
  sole writer of `loop_count`, `max_loops`, `stalled_reason`, and `pr_url`. `/sort-task`
  reads them to render the board.
- **Auto mode is opt-in**, triggered by phrases like "auto", "launch everything",
  "launch ready tasks", "auto-dequeue". In auto mode `/launch-task` creates worktrees,
  spawns parallel code sub-agents, and never asks for confirmation. In manual mode
  `/launch-task` suggests the top 3 ready candidates and waits for the user to pick.
