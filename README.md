# Banking — Implementation Repo for Reliever

This repo is the **implementation side** of Reliever, a financial-inclusion product.
It contains the tactical process model of every business capability, its roadmap,
its tasks, and the generated source code and tests.

All upstream knowledge (BCM YAML, GOV / URBA / FUNC / TECH-STRAT / TECH-TACT ADRs,
product / business / tech visions) lives in the external **`banking-knowledge`**
repository and is consumed **read-only** through the `bcm-pack` CLI. This repo never
authors or modifies upstream artifacts.

---

## The implementation pipeline

```
                 ┌──────────────────────────────────────────────────────────┐
                 │ Upstream — banking-knowledge repo (read-only via bcm-pack)│
                 │                                                          │
                 │  product → strategic → tech → FUNC ADR → tactical ADR    │
                 │   vision    business    vision    (per L2)    (per L2)   │
                 │             vision                                       │
                 │                              ↓                           │
                 │                          BCM YAML                        │
                 └──────────────────────────────────────────────────────────┘
                                              │
                                              │  bcm-pack pack <CAP_ID> --deep
                                              ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ This repo — the implementation pipeline                                 │
   │                                                                         │
   │  [0] process   [1] roadmap [2] task    [3] sort-task    [4] code        │
   │      ─────▶        ─────▶      ─────▶      / launch         ─────▶      │
   │      │             │           │           │                │           │
   │   process/      roadmap/    tasks/      tasks/           worktree       │
   │   <CAP>/        <CAP>/      <CAP>/      BOARD.md         + agents       │
   │   (PR gate)     roadmap.md  TASK-*.md  + scheduler          │           │
   │                                                             ▼           │
   │                                                       [5] test          │
   │                                                       (zone-aware)      │
   │                                                             │           │
   │                                                             ▼           │
   │                                                       PR + status:      │
   │                                                       in_review         │
   └────────────────────────────────────────────────────────────────────────┘
```

The pipeline is **launched and resumed** through one entry point:

```
/implementation-pipeline
```

It probes upstream readiness via `bcm-pack`, inspects local artifacts, and
dispatches the next pending stage. It is idempotent — re-invoke after each
stage completes to advance.

---

## What `/implementation-pipeline` actually does

When you invoke the skill it:

1. **Probes upstream readiness** for each capability:
   ```bash
   bcm-pack pack <CAP_ID> --deep --compact > /tmp/probe.json
   jq '.slices'  /tmp/probe.json   # all required slices must be non-empty
   jq '.warnings' /tmp/probe.json  # must be empty
   ```
   Required slices: `product_vision`, `business_vision`, `tech_vision`,
   `governing_tech_strat`, `capability_definition`, `tactical_stack`,
   `capability_self`. If any is empty or `warnings` is non-empty, the
   skill stops and redirects you to the upstream repo.

2. **Inspects local artifacts** with `ls` — never touches `/bcm/`, `/func-adr/`,
   `/adr/`, `/strategic-vision/`, `/product-vision/`, `/tech-vision/`, `/tech-adr/`
   (those are upstream and not authoritative locally).

3. **Reports per-capability status** as a table of ✅ / ⏳ / ⬜ across the six
   stages, and names the next action.

4. **Dispatches the cheapest pending stage**:

   | Pending state | Action |
   |---|---|
   | Capabilities with a complete `bcm-pack` slice but no `process/<CAP_ID>/` on `main` | Tells you to run `/process <CAP_ID>` (interactive — drives the modelling session and opens a PR) |
   | Capabilities with `process/` merged but no `roadmap.md` | Spawns one `/roadmap` subagent per capability, in parallel |
   | Capabilities with a roadmap but no tasks | Spawns one `/task` subagent per capability, in parallel |
   | Tasks exist | Hands off to `/launch-task` (which calls `/sort-task` first) |

5. **Stops driving execution at Stage 3**. From there `/launch-task` is the
   scheduler and `/code` is the worker — see below.

---

## The six stages

### Stage 0 — Process (DDD tactical model)

| | |
|---|---|
| **Skill** | `/process` |
| **Reads** | `bcm-pack pack <CAP_ID> --deep` (BCM + FUNC / URBA / TECH-STRAT ADRs + visions) |
| **Writes** | `process/<CAP_ID>/` — `aggregates.yaml`, `commands.yaml`, `policies.yaml`, `read-models.yaml`, `bus.yaml`, `api.yaml`, `schemas/CMD.*.schema.json`, `schemas/RVT.*.schema.json`, `README.md` |
| **Branch** | dedicated `process/<CAP_ID>` in a worktree under `/tmp/process-worktrees/<CAP_ID>/` |
| **Publication** | the skill commits, pushes, and opens a PR titled `process(<CAP_ID>): …` against `main` |

This is the **DDD tactical layer** that bridges Big-Picture Event Storming (the
upstream BCM/ADR corpus) and Software Design (the rest of the pipeline). It
captures aggregates with their invariants, the commands they accept, the
policies that wire consumed events to commands, the read-models that project
the domain events, and the RabbitMQ topology of every event published or
consumed — all in architecture-neutral YAML.

`/process` is the **only** authority on `process/<CAP_ID>/`. A `PreToolUse`
hook (`process-folder-guard.py`) blocks every Write/Edit attempt under
`process/**` from any other skill or agent.

**Readiness gate** — `/roadmap`, `/task`, `/launch-task`, `/code`, and `/fix`
all refuse to run for a capability whose `process/<CAP_ID>/` is missing on
`main` or whose `process/<CAP_ID>` PR is still open. Downstream stages only
consume process models that have been reviewed and merged.

### Stage 1 — Roadmap

| | |
|---|---|
| **Skill** | `/roadmap` |
| **Reads** | `bcm-pack pack <CAP_ID> --deep` + `process/<CAP_ID>/` (read-only) |
| **Writes** | `roadmap/<CAP_ID>/roadmap.md` (epics, milestones, exit conditions) |
| **Parallelism** | one subagent per capability |

Roadmaps are epic-level: they decompose a capability into business outcomes
with explicit exit conditions that a downstream task can prove. The roadmap
references the AGG / CMD / POL / PRJ / QRY identifiers from the process
model — it never re-derives them.

### Stage 2 — Task

| | |
|---|---|
| **Skill** | `/task` |
| **Reads** | `roadmap/<CAP_ID>/roadmap.md` + `process/<CAP_ID>/` + `bcm-pack pack <CAP_ID> --compact` |
| **Writes** | `tasks/<CAP_ID>/TASK-NNN-*.md` (flat per-capability folder) |
| **Frontmatter** | `task_id`, `capability_id`, `epic`, `status`, `priority`, `depends_on`, `task_type?`, `loop_count: 0`, `max_loops: 10` |
| **Parallelism** | one subagent per capability |

Tasks are unit-of-work-level: each carries a Definition of Done (DoD) that the
test stage will mechanically check off.

### Stage 3a — sort-task (read-only board)

| | |
|---|---|
| **Skill** | `/sort-task` |
| **Reads** | all `tasks/**/TASK-*.md` |
| **Writes** | `tasks/BOARD.md` |
| **Computes** | `ready` / `blocked` / `needs_info` / `stalled` / `in_progress` / `in_review` / `done` |
| **Auto-run** | PostToolUse hook on every TASK file change |

Pure observation. Never modifies tasks, never launches agents.

### Stage 3b — launch-task (scheduler)

| | |
|---|---|
| **Skill** | `/launch-task` |
| **Calls first** | `/sort-task` (to get fresh kanban state) |
| **Picks** | ready task by `critical_path × priority` |
| **Spawns** | one `/code` sub-agent per task |
| **Modes** | manual (suggest top 3) / reactive (on `ready` transition) / `auto` (parallel autonomous) |
| **Isolation** | each task gets its own git worktree at `/tmp/kanban-worktrees/TASK-NNN-{slug}/` on branch `feat/TASK-NNN-{slug}` |
| **Idempotency** | at most one `/code` agent per task at a time; at most one active task per capability |

### Stage 4 — Code (zone-aware)

| | |
|---|---|
| **Skill** | `/code` |
| **Reads** | task file + `process/<CAP_ID>/` + `bcm-pack pack <CAP_ID>` (for `zoning`) |
| **Branches on** | `task_type` (`contract-stub` → Mode B), then capability `zoning` |

| Routing | Path | Agent(s) | Output |
|---|---|---|---|
| `task_type: contract-stub` (any zone) | C | `implement-capability` (Mode B) | `sources/<CAP_ID>/stub/` — minimal .NET worker that publishes RVT events on RabbitMQ. **Reads** the JSON Schemas from `process/<CAP_ID>/schemas/RVT.*.schema.json` (does not regenerate them) |
| `BUSINESS_SERVICE_PRODUCTION` `SUPPORT` `REFERENTIAL` `EXCHANGE_B2B` `DATA_ANALYTIQUE` `STEERING` | A | `implement-capability` (Mode A) | `sources/<CAP_ID>/backend/` — .NET 10 microservice (Domain / Application / Infrastructure / Presentation / Contracts), MongoDB, RabbitMQ, `GET /health` |
| `CHANNEL` | B | `create-bff` ∥ `code-web-frontend` (parallel) | `sources/<CAP_ID>/bff/` (.NET 10 ASP.NET Core BFF) + `sources/<CAP_ID>/frontend/` (vanilla HTML5 + CSS3 + JS) |

After implementation, `/code` invokes the matching test skill (Stage 5) and
runs a remediation loop: failing tests feed back into the implementation
agent with a `── REMEDIATION CONTEXT ──` block. The loop is bounded by
`max_loops` (default 10). Exhaustion → `status: stalled`, resumable via
`/continue-work TASK-NNN [--max-loops N]`.

For non-CHANNEL Mode A, an optional **contract harness** can be attached
post-implementation via `/harness-backend <CAP_ID>` — it scaffolds a
`*.Contracts.Harness/` project that derives `openapi.yaml` and `asyncapi.yaml`
from `process/<CAP_ID>/` and the BCM corpus, and asserts strict alignment
with bidirectional `x-lineage` extensions.

**Branch isolation is end-to-end**: bus channels, RabbitMQ exchanges/queues,
OTel `environment` tag, frontend branch badge all carry the branch slug.
Concurrent worktrees never collide on infrastructure.

### Stage 5 — Test (zone-aware)

| | Path A — non-CHANNEL | Path B — CHANNEL |
|---|---|---|
| **Skill** | `/test-business-capability` | `/test-app` |
| **Agent** | `test-business-capability` | `test-app` |
| **Stack** | .NET service + MongoDB + RabbitMQ via docker-compose | static HTTP server (frontend) + .NET BFF + RabbitMQ |
| **Modes** | backend-only | `full-mock` / `frontend+bff` / `bff-only` |
| **Workdir** | `/tmp/test-<cap-id>-XXXXXX` (ephemeral) | `/tmp/test-app-<cap-id>-XXXXXX` (ephemeral) |
| **Generates** | `tests/<CAP_ID>/TASK-NNN-{slug}/{conftest.py, test_dod.py, test_business_rules.py, test_strategic.py, test_backend.py}` | `…/{conftest.py, test_dod.py, test_business_rules.py, test_strategic.py, test_bff.py?}` |
| **Asserts** | REST endpoints, persistence, RabbitMQ event emission, OTel tags | DOM order (dignity rule), Playwright DoD checks, BFF `/health` + ETag/304 |

Both paths produce `report.html` + `run.log`, translate pytest results into
business language (✅/❌ per DoD criterion), and tear down all spawned
processes. Original artifacts are never modified.

On success: `status: in_review`, `pr_url:` written to frontmatter, branch
pushed, `gh pr create` with DoD checklist + local-stack instructions
(including `LOCAL_PORT`, `MONGO_PORT`, `RABBIT_PORT`, `RABBIT_MGMT_PORT`,
`BFF_PORT`).

---

## Repo layout

```
/CLAUDE.md                            contributor & Claude Code guidance
/README.md                            this file
/process/                             local — DDD tactical model (Stage 0)
   <CAP_ID>/README.md                 framing + scenario walkthroughs + open questions
   <CAP_ID>/aggregates.yaml           consistency boundaries + invariants
   <CAP_ID>/commands.yaml             accepted commands + idempotency
   <CAP_ID>/policies.yaml             event → command reactive policies
   <CAP_ID>/read-models.yaml          projections + queries
   <CAP_ID>/bus.yaml                  RabbitMQ topology (publish + subscribe)
   <CAP_ID>/api.yaml                  derived REST surface
   <CAP_ID>/schemas/                  JSON Schemas (CMD.*.schema.json, RVT.*.schema.json)
   banking-miro.url                   live link to the Miro Event Storming board
/roadmap/                             local — epic roadmaps (Stage 1)
   <CAP_ID>/roadmap.md                epics + milestones + exit conditions
/tasks/                               local — kanban (Stages 2-3)
   BOARD.md                           kanban (auto-refreshed via hook)
   <CAP_ID>/TASK-NNN-*.md             unit-of-work + DoD + frontmatter
/sources/                             local — implementation artifacts (Stage 4)
   <CAP_ID>/backend/                  non-CHANNEL .NET 10 microservice
   <CAP_ID>/stub/                     contract-stub Mode B worker
   <CAP_ID>/bff/                      CHANNEL .NET 10 ASP.NET Core BFF
   <CAP_ID>/frontend/                 CHANNEL vanilla HTML/CSS/JS
/tests/<CAP_ID>/TASK-NNN-{slug}/      generated pytest suite + report.html
/.claude/
   skills/                            Claude Code skills (this orchestrator + the workers)
      implementation-pipeline/        the orchestrator
      process/                        Stage 0 — interactive modelling + PR
      roadmap/  task/  sort-task/     stages 1-3a
      launch-task/  code/             stages 3b-4
      test-business-capability/       stage 5 — Path A
      test-app/                       stage 5 — Path B
      task-refinement/                resolve a TASK's open questions
      continue-work/                  resume a `stalled` task
      fix/                            remediate a failing PR / merged build
      harness-backend/                add OpenAPI + AsyncAPI contract harness
      sketch-miro/                    render process/ as a Miro Event Storming board
      pr-merge-watcher/  agent-watch/ ops helpers
      commit/                         conventional-commit + push + PR helper
   agents/                            agent definitions
      implement-capability.md         non-CHANNEL backend (Modes A & B)
      create-bff.md                   CHANNEL BFF
      code-web-frontend.md            CHANNEL frontend
      test-business-capability.md     stage-5 test agent — Path A
      test-app.md                     stage-5 test agent — Path B
      harness-backend.md              contract harness generator
   hooks/
      process-folder-guard.py         PreToolUse — protects process/** outside /process
      kanban-watch-write.sh           PostToolUse — refresh BOARD on TASK file edit
      kanban-watch-bash.sh            PostToolUse — refresh BOARD on TASK rm/mv
```

---

## Skill cheatsheet

| Command | What it does |
|---|---|
| `/implementation-pipeline` | Status + advance to next pending stage |
| `/process <CAP_ID>` | Stage 0 — interactive DDD modelling, opens a PR on `process/<CAP_ID>` branch |
| `/sketch-miro` | Render every `process/CAP.*/` as a Miro Event Storming board |
| `/roadmap` | Stage 1 — generate `roadmap.md` for current capability |
| `/task` | Stage 2 — generate `TASK-NNN-*.md` for a capability |
| `/sort-task` | Refresh `tasks/BOARD.md` (read-only) |
| `/launch-task` | Stage 3+ — pick a ready task, spawn `/code` |
| `/launch-task auto` | Stage 3+ — autonomous parallel, all ready tasks |
| `/code TASK-NNN` | Stage 4-5 for one task (zone-aware dispatch) |
| `/test-business-capability TASK-NNN` | Stage 5 only — Path A |
| `/test-app TASK-NNN` | Stage 5 only — Path B |
| `/harness-backend <CAP_ID>` | Add the OpenAPI + AsyncAPI contract harness to a non-CHANNEL service |
| `/fix <PR# \| TASK-NNN \| logs>` | Remediate a failing PR or post-merge breakage on the existing branch |
| `/task-refinement TASK-NNN` | Resolve open questions on a task |
| `/continue-work TASK-NNN` | Resume a `stalled` task with reset loop counter |
| `/pr-merge-watcher` | Transition `in_review` tasks to `done` after PR merge; auto-dispatch `/fix` on red CI |
| `/agent-watch [TASK-NNN]` | Live tmux view of a running code agent |
| `/commit` | Conventional-commit + push (+ optional PR draft) |

---

## Invariants

- **All upstream context is read-only.** GOV / URBA / TECH-STRAT / FUNC / TACTICAL
  ADRs, BCM YAML, and product/business/tech visions are consumed via `bcm-pack`
  only. To change them, edit the `banking-knowledge` repo.
- **`process/<CAP_ID>/` is owned by `/process`.** No other skill or agent may
  modify it; a `PreToolUse` hook enforces this. Changes flow through a
  dedicated `process/<CAP_ID>` PR and must be merged before downstream stages
  can consume the model — `/roadmap`, `/task`, `/launch-task`, `/code`, and
  `/fix` all gate on this.
- **Folder layout is strict.** The legacy `/plan/` output folder no longer
  exists. `/process/` (Stage 0), `/roadmap/` (Stage 1), `/tasks/` (Stages 2–3)
  each have a single authoring skill. No skill writes outside its lane.
- **Every task traces back** to a roadmap epic → process model → BCM capability →
  FUNC ADR → URBA constraints. The chain is unbreakable.
- **Every implementation artifact** (microservice / BFF / frontend / stub) is
  reachable from a TASK-NNN, and every routing key / aggregate / command it uses
  is defined in `process/<CAP_ID>/`.
- **Branch isolation** — one branch per task, ports & exchanges scoped by branch
  slug, parallel worktrees never collide.
- **One code agent per task** at a time; one active task per capability.
- **Loop counters live on the TASK file**, not on the board. The code skill is the
  sole writer of `loop_count`, `max_loops`, `stalled_reason`, `pr_url`.

---

## Special task states

| Glyph | State | Meaning | Resolution |
|---|---|---|---|
| 🟢 | `ready` | All deps `done`, no open questions | `/launch-task` picks it up |
| 🟡 | `in_progress` | A `/code` agent is working in a worktree | `/agent-watch TASK-NNN` to observe |
| 🟣 | `in_review` | PR open, awaiting merge | `/pr-merge-watcher` flips to `done` on merge |
| ⚫ | `stalled` | `max_loops` exhausted with failing tests | `/continue-work TASK-NNN [--max-loops N]` |
| 🟠 | `needs_info` | Open questions in TASK file | resolve inline or `/task-refinement TASK-NNN` |
| 🔵 | `blocked` | A dep is not `done` | wait, or unblock the dep |
| ✅ | `done` | PR merged | — |
