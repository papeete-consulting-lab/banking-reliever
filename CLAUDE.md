# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## What this repo is

This is the **implementation side** of *Reliever*, a financial-inclusion product.
It turns validated business capabilities into runnable .NET microservices, BFFs,
vanilla web frontends, contract stubs, and their tests.

All upstream knowledge — BCM YAML, GOV / URBA / TECH-STRAT / FUNC / TECH-TACT
ADRs, product / business / tech visions — lives in a separate
**`banking-knowledge`** repo and is consumed **read-only** through the
`bcm-pack` CLI. This repo never authors or edits upstream artifacts. There is
no `bcm/`, `adr/`, `func-adr/`, `tools/`, `build.sh`, or EventCatalog build
here anymore.

## The implementation pipeline

Six stages, each owned by a single skill, each writing to a single folder:

```
[0] /process       process/<CAP_ID>/          DDD tactical model (PR-gated)
[1] /roadmap       roadmap/<CAP_ID>/          epics + milestones
[2] /task          tasks/<CAP_ID>/            unit-of-work TASK-NNN-*.md
[3] /sort-task     tasks/BOARD.md             read-only kanban (hook-driven)
    /launch-task   /tmp/kanban-worktrees/…    scheduler — spawns /code agents
[4] /code          sources/<CAP_ID>/…         zone-aware implementation
                                              (backend/ | stub/ | bff/ | frontend/)
[5] /test-*        tests/<CAP_ID>/…           pytest + report.html
```

Entry point for end-to-end orchestration: **`/implementation-pipeline`** —
probes upstream readiness via `bcm-pack`, inspects local artifacts, dispatches
the next pending stage. Idempotent: re-invoke after each stage completes.

## Repo layout

```
/process/<CAP_ID>/        Stage 0 — aggregates.yaml, commands.yaml, policies.yaml,
                          read-models.yaml, bus.yaml, api.yaml, schemas/*.schema.json
/roadmap/<CAP_ID>/        Stage 1 — roadmap.md
/tasks/                   Stages 2-3 — BOARD.md + <CAP_ID>/TASK-NNN-*.md
/sources/<CAP_ID>/        Stage 4 — backend/ (Mode A microservice) | stub/ (Mode B)
                                  | bff/ (CHANNEL BFF) | frontend/ (CHANNEL SPA)
/tests/<CAP_ID>/TASK-NNN-{slug}/   Stage 5 — generated pytest suite + report.html
/docs/c4/                 Structurizr DSL — enterprise/workspace.dsl, enterprise/zone-*.dsl,
                          <CAP_L2>/workspace.dsl (owned by /c4-export)
/externals-template/      seed templates for the application & process catalogues
/.claude/skills/          one folder per skill (see cheatsheet)
/.claude/agents/          implement-capability, create-bff, code-web-frontend,
                          test-business-capability, test-app, harness-backend
/.claude/hooks/           process-folder-guard.py, kanban-watch-*.sh
```

## TASK frontmatter

```yaml
task_id: TASK-NNN
capability_id: CAP.<ZONE>.<NNN>[.<SUB>]
epic: <epic-id>
status: todo | ready | in_progress | in_review | done | blocked | needs_info | stalled
priority: <int>
depends_on: [TASK-NNN, …]
task_type: full-microservice | contract-stub   # optional, defaults to full
loop_count: 0
max_loops: 10
pr_url: <set by /code on PR creation>
```

`/code` is the sole writer of `loop_count`, `max_loops`, `stalled_reason`, `pr_url`.

## Stage 4 routing (zone-, type-, and language-aware)

Zone is read from `bcm-pack pack <CAP_ID>` (`slices.capability_self[0].zoning`) —
never inferred from the capability ID prefix. The implementation
language for Path A and Path C is read from the **TECH-TACT ADR** of
the capability (`slices.tactical_stack[0].tags`) — `python` /
`fastapi` route to the Python agent, `dotnet` / `csharp` / `aspnet`
route to the .NET agent. If no TECH-TACT ADR is published yet, `/code`
falls back to the .NET agent with a warning.

| Trigger | Agent(s) | Output |
|---|---|---|
| `task_type: contract-stub` + TECH-TACT tag `python` | `implement-capability-python` (Mode B) | `sources/<CAP_ID>/stub/` — FastAPI app publishing RVT events via `aio-pika` + canned-fixture query API; reads schemas from `process/<CAP_ID>/schemas/` (does NOT regenerate them) |
| `task_type: contract-stub` + TECH-TACT tag `dotnet` (default) | `implement-capability` (Mode B) | `sources/<CAP_ID>/stub/` — minimal .NET worker + Minimal-API host; schemas read from `process/<CAP_ID>/schemas/` |
| zone ∈ {`BUSINESS_SERVICE_PRODUCTION`, `SUPPORT`, `REFERENTIAL`, `EXCHANGE_B2B`, `DATA_ANALYTIQUE`, `STEERING`} + TECH-TACT tag `python` | `implement-capability-python` (Mode A) | `sources/<CAP_ID>/backend/` — Python 3.12+ microservice (Domain / Application / Infrastructure / Presentation / Contracts packages), FastAPI, motor or psycopg/asyncpg, aio-pika |
| same zones + TECH-TACT tag `dotnet` (default) | `implement-capability` (Mode A) | `sources/<CAP_ID>/backend/` — .NET 10 microservice (Domain / Application / Infrastructure / Presentation / Contracts), MongoDB, RabbitMQ |
| zone = `CHANNEL` | `create-bff` ∥ `code-web-frontend` (parallel) | `sources/<CAP_ID>/bff/` (.NET 10 Minimal API BFF) + `sources/<CAP_ID>/frontend/` (vanilla HTML5/CSS3/JS) — language fixed; TECH-TACT tags ignored for CHANNEL |

Post-implementation:
- Stage 5 runs automatically (`test-business-capability` for non-CHANNEL,
  `test-app` for CHANNEL). Failure feeds back into the implementation agent
  via a `── REMEDIATION CONTEXT ──` block, bounded by `max_loops`.
- For non-CHANNEL Mode A, an optional **contract harness** is attached via
  `/harness-backend <CAP_ID>` — scaffolds a `*.Contracts.Harness/` project
  that derives `openapi.yaml` + `asyncapi.yaml` from `process/<CAP_ID>/`
  and the BCM corpus, with bidirectional `x-lineage` extensions.

## Skill cheatsheet

| Command | What it does |
|---|---|
| `/implementation-pipeline` | Status across all capabilities; advance to next pending stage |
| `/process <CAP_ID>` | Stage 0 — interactive DDD modelling; opens PR on `process/<CAP_ID>` branch |
| `/sketch-miro` | Render every `process/CAP.*/` as a Miro Event Storming board |
| `/c4-export` | Render the BCM tree as Structurizr DSL — per-L2, per-zone, enterprise — under `docs/c4/` |
| `/roadmap` | Stage 1 — `roadmap.md` for a capability |
| `/task` | Stage 2 — `TASK-NNN-*.md` for a capability |
| `/sort-task` | Refresh `tasks/BOARD.md` (read-only) |
| `/launch-task` | Pick a ready task, spawn `/code` in an isolated worktree |
| `/launch-task auto` | Parallel autonomous launch of all ready tasks |
| `/code TASK-NNN` | Stage 4-5 for one task (zone-aware dispatch) |
| `/test-business-capability TASK-NNN` | Stage 5 — Path A (backend microservice) |
| `/test-app TASK-NNN` | Stage 5 — Path B (CHANNEL frontend + BFF) |
| `/harness-backend <CAP_ID>` | Add OpenAPI + AsyncAPI contract harness to a Mode-A service |
| `/fix <PR# \| TASK-NNN \| logs>` | Remediate a failing PR or post-merge breakage on the existing branch |
| `/task-refinement TASK-NNN` | Resolve open questions on a task |
| `/continue-work TASK-NNN [--max-loops N]` | Resume a `stalled` task with reset loop counter |
| `/pr-merge-watcher` | `in_review` → `done` after PR merge; auto-dispatch `/fix` on red CI |
| `/agent-watch [TASK-NNN]` | Live tmux view of a running `/code` agent |
| `/commit` | Conventional-commit + push (+ optional PR draft) |

## Invariants

- **Upstream is read-only.** Never read `/bcm/`, `/adr/`, `/func-adr/`,
  `/strategic-vision/`, `/product-vision/`, `/tech-vision/`, `/tech-adr/`
  from disk — they don't live here. Use `bcm-pack pack <CAP_ID> [--deep] [--compact]`.
- **`process/<CAP_ID>/` is owned by `/process` alone.** A PreToolUse hook
  (`process-folder-guard.py`) blocks every Write/Edit under `process/**`
  from any other skill or agent. Changes flow through a dedicated
  `process/<CAP_ID>` PR; `/roadmap`, `/task`, `/launch-task`, `/code`, `/fix`
  refuse to run until that PR is merged into `main`.
- **One authoring skill per folder.** `/process` → `process/`, `/roadmap` → `roadmap/`,
  `/task` → `tasks/<CAP_ID>/`, `/sort-task` → `tasks/BOARD.md`, `/code` → `sources/`
  and `src/`, the test skills → `tests/`, `/c4-export` → `docs/c4/`. No skill writes
  outside its lane.
- **Branch isolation is end-to-end.** One branch (`feat/TASK-NNN-{slug}`) and
  one worktree (`/tmp/kanban-worktrees/TASK-NNN-{slug}/`) per task. RabbitMQ
  exchanges/queues, ports, OTel `environment` tag, and frontend branch badge
  all carry the branch slug — concurrent worktrees never collide.
- **One `/code` agent per task; one active task per capability.**
- **Loop counters live on the TASK file**, not on the board.
- **Every artifact traces back** to a TASK → roadmap epic → process model →
  BCM capability → FUNC ADR → URBA constraints. The chain is unbreakable.

## Task states

| Glyph | State | Meaning | Resolution |
|---|---|---|---|
| 🟢 | `ready` | All deps `done`, no open questions | `/launch-task` picks it up |
| 🟡 | `in_progress` | A `/code` agent is working in a worktree | `/agent-watch TASK-NNN` |
| 🟣 | `in_review` | PR open, awaiting merge | `/pr-merge-watcher` flips to `done` on merge |
| ⚫ | `stalled` | `max_loops` exhausted with failing tests | `/continue-work TASK-NNN [--max-loops N]` |
| 🟠 | `needs_info` | Open questions in TASK file | resolve inline or `/task-refinement TASK-NNN` |
| 🔵 | `blocked` | A dep is not `done` | wait, or unblock the dep |
| ✅ | `done` | PR merged | — |

## When you don't know where to start

- New capability, never modelled here → `/implementation-pipeline` (it will
  tell you to run `/process <CAP_ID>` first, after checking `bcm-pack` readiness).
- Process model merged, no roadmap yet → `/roadmap`.
- Roadmap merged, no tasks → `/task`.
- Tasks exist → `/launch-task` (or `/launch-task auto`).
- Something is red → `/fix` with the PR number, branch, or log paste.
