# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## What this repo is

This is the **implementation side** of *Reliever*, a financial-inclusion product.
It turns validated business capabilities into runnable .NET microservices, BFFs,
vanilla web frontends, contract stubs, and their tests.

All upstream knowledge — BCM YAML, GOV / URBA / TECH-STRAT / FUNC / TECH-TACT
ADRs, product / business / tech visions — lives in a separate
**`reliever-knowledge`** repo and is consumed **read-only** through the
`rlv-knowledge` CLI. (The GOV ADRs surfaced here are scoped to the **Reliever
product** — see the governance substrate below for the organisation-wide ones.)
**The DDD tactical Process Modelling layer** (aggregates,
commands, policies, read-models, bus topology, JSON Schemas) also lives in
`reliever-knowledge` now (authored there by the `/process` skill) and is
consumed here **read-only** through `rlv-knowledge process <CAP_ID>` — exactly like
the BCM corpus (see `reliever-knowledge` for the migration rationale). The
runtime/deployment **platform** substrate (PCM model, platform events/objects,
runtime ADRs) lives in a second separate repo, **`banking-tech`**, consumed
**read-only** through the `tech` CLI (its GOV ADRs are scoped to the **tech**
platform). The **organisation-wide governance** substrate — enterprise-level
GOV ADRs that sit above any single product or platform — lives in a third
separate repo, **`banking-governance`**
(`Banking-PapeeteConsulting/banking-governance`), consumed **read-only**
through the `gov` CLI. So governance is layered across three scopes and three
sources: org-wide via `gov`, Reliever-product-scoped via `rlv-knowledge`,
tech-platform-scoped via `tech`. This repo never authors or edits
upstream artifacts. There is no `bcm/`, `adr/`, `func-adr/`, `process/`,
`tools/`, `build.sh`, or EventCatalog build here anymore.

### Enriched, source-context-prefixed asset IDs (CLI v2.0.0+)

Every upstream asset ID now carries an **`<ENTERPRISE>.<SCOPE>.`
source-context prefix** (governed by `ADR-PCM-URBA-0014` — now owned by the
`banking-governance` repo as an org-wide governance ADR; it keeps its legacy
`PCM` name until the upstream cleanup renames it. Tech-repo ADRs likewise still
adhere to the `PCM` naming):

```
CAP.<ZONE>.<NNN>[.<CODE>]   →   BNK.RLVR.CAP.<ZONE>.<NNN>[.<CODE>]   (knowledge / rlv-knowledge)
RVT.<ZONE>.<NNN>.<NAME>     →   BNK.RLVR.RVT.<ZONE>.<NNN>.<NAME>     (resource events)
EVT.<ZONE>.<NNN>.<NAME>     →   BNK.RLVR.EVT.<ZONE>.<NNN>.<NAME>     (business events)
OBJ.… / SUB.… / RES.… / CON.…  →  BNK.RLVR.OBJ.… / BNK.RLVR.SUB.… / …
```

Platform (PCM) assets use the **`BNK.TECH.`** prefix instead of `BNK.RLVR.`.

Rules:
- **The capability ID is the full prefixed form everywhere in this repo** —
  folder names (`sources/BNK.RLVR.CAP.…/`, `roadmap/BNK.RLVR.CAP.…/`, …),
  `capability_id` in TASK frontmatter, branch derivation, the argument to
  `rlv-knowledge process`, and all skill/agent docs. `rlv-knowledge`/`tech` v2.0.0
  **reject the old short form** (`CAP.…`) with exit code 2 (`Unknown capability`).
- **bcm-sourced asset IDs** (`CAP/RVT/EVT/OBJ/SUB/RES/CON`) are used **verbatim
  as returned by `rlv-knowledge`** — already prefixed. Schemas, `bus.yaml` routing
  keys, generated event classes, and RabbitMQ topology all carry the prefix.
- **Process-authored tactical IDs** (`AGG/CMD/POL/PRJ/QRY` — invented by
  `/process`, not present in BCM) remain **capability-local / unprefixed**.

### Versioned knowledge (CLI v2.0.0+)

Both CLIs surface knowledge-base provenance and a semantic diff:

```
rlv-knowledge version [--compact]                       # KB provenance JSON
rlv-knowledge diff <from_ref> [--to <ref>] [--capability <CAP_ID>] [--compact]
rlv-knowledge pack <CAP_ID> …                            # now embeds a top-level
                                                    # "knowledge_base" block
```

`version`/`pack.knowledge_base` fields: `package_version`, `source`, `ref`,
`branch`, `commit`, `commit_short`, `committed_at`, `dirty`. The `diff`
envelope reports added/removed/changed counts per asset family (capabilities,
business/resource events, objects, concepts, resources, subscriptions, ADRs,
vocab) — scoped to one capability with `--capability`.

**Provenance is recorded and drift is detected** (see invariants): `/process`
(upstream) stamps the consumed `knowledge_base` block into the process model;
`rlv-knowledge process <CAP_ID>` surfaces it as `.knowledge_base`; downstream
artifacts carry the `bcm_ref` forward; `/implementation-pipeline` and `/fix`
run `rlv-knowledge diff <recorded_ref> --capability <CAP_ID>` to flag when upstream
knowledge has moved since an artifact was generated.

## The implementation pipeline

Stage 0 — the DDD tactical **Process Modelling** layer — is authored by
`/process` **in the `reliever-knowledge` repo** and consumed here read-only via
`rlv-knowledge process <CAP_ID>`. The five local stages, each owned by a single
skill, each writing to a single folder:

```
[0] /process       (reliever-knowledge)        DDD tactical model
                   ↳ consumed here via `rlv-knowledge process <CAP_ID>` (read-only)
[1] /roadmap       roadmap/<CAP_ID>/          epics + milestones
[2] /task          tasks/<CAP_ID>/            unit-of-work TASK-NNN-*.md
[3] /sort-task     tasks/BOARD.md             read-only kanban (hook-driven)
    /launch-task   /tmp/kanban-worktrees/…    scheduler — spawns /code agents
[4] /code          sources/<CAP_ID>/…         zone-aware implementation
                                              (backend/ | stub/ | bff/ | frontend/)
[5] /test-*        tests/<CAP_ID>/…           pytest + report.html
```

Entry point for end-to-end orchestration: **`/implementation-pipeline`** —
probes upstream readiness via `rlv-knowledge` (knowledge) and `rlv-knowledge process`
(the process model), inspects local artifacts, dispatches the next pending
stage. Idempotent: re-invoke after each stage completes.

## Repo layout

```
(Stage 0 — process model — is NOT here; fetch via `rlv-knowledge process <CAP_ID>`.
 It lives in the reliever-knowledge repo, authored by /process.)
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
/.claude/hooks/           roadmap-folder-guard.py, tasks-folder-guard.py, kanban-watch-*.sh
```

## TASK frontmatter

```yaml
task_id: TASK-NNN
capability_id: BNK.RLVR.CAP.<ZONE>.<NNN>[.<CODE>]   # full source-context-prefixed ID
epic: <epic-id>
status: todo | ready | in_progress | in_review | done | blocked | needs_info | stalled
priority: <int>
depends_on: [TASK-NNN, …]
task_type: full-microservice | contract-stub   # optional, defaults to full
loop_count: 0
max_loops: 10
pr_url: <set by /code on PR creation>
bcm_ref: <git ref the process model was generated from, e.g. v2.0.0>   # set by /task, carried from process provenance
```

`/code` is the sole writer of `loop_count`, `max_loops`, `stalled_reason`, `pr_url`.
`bcm_ref` is carried forward from the process-model provenance (stamped by
`/process` upstream, surfaced as `rlv-knowledge process <CAP_ID>` → `.knowledge_base.ref`)
so any stage can `rlv-knowledge diff` against it to detect upstream drift.

## Stage 4 routing (zone-, type-, and language-aware)

Zone is read from `rlv-knowledge pack <CAP_ID>` (`slices.capability_self[0].zoning`) —
never inferred from the capability ID prefix. The implementation
language for Path A and Path C is read from the **TECH-TACT ADR** of
the capability (`slices.tactical_stack[0].tags`) — `python` /
`fastapi` route to the Python agent, `dotnet` / `csharp` / `aspnet`
route to the .NET agent. If no TECH-TACT ADR is published yet, `/code`
falls back to the .NET agent with a warning.

| Trigger | Agent(s) | Output |
|---|---|---|
| `task_type: contract-stub` + TECH-TACT tag `python` | `implement-capability-python` (Mode B) | `sources/<CAP_ID>/stub/` — FastAPI app publishing RVT events via `aio-pika` + canned-fixture query API; reads schemas from `rlv-knowledge process <CAP_ID>` (`.schemas`, does NOT regenerate them) |
| `task_type: contract-stub` + TECH-TACT tag `dotnet` (default) | `implement-capability` (Mode B) | `sources/<CAP_ID>/stub/` — minimal .NET worker + Minimal-API host; schemas read from `rlv-knowledge process <CAP_ID>` (`.schemas`) |
| zone ∈ {`BUSINESS_SERVICE_PRODUCTION`, `SUPPORT`, `REFERENTIAL`, `EXCHANGE_B2B`, `DATA_ANALYTICS`, `STEERING`} + TECH-TACT tag `python` | `implement-capability-python` (Mode A) | `sources/<CAP_ID>/backend/` — Python 3.12+ microservice (Domain / Application / Infrastructure / Presentation / Contracts packages), FastAPI, motor or psycopg/asyncpg, aio-pika |
| same zones + TECH-TACT tag `dotnet` (default) | `implement-capability` (Mode A) | `sources/<CAP_ID>/backend/` — .NET 10 microservice (Domain / Application / Infrastructure / Presentation / Contracts), MongoDB, RabbitMQ |
| zone = `CHANNEL` | `create-bff` ∥ `code-web-frontend` (parallel) | `sources/<CAP_ID>/bff/` (.NET 10 Minimal API BFF) + `sources/<CAP_ID>/frontend/` (vanilla HTML5/CSS3/JS) — language fixed; TECH-TACT tags ignored for CHANNEL |

Post-implementation:
- Stage 5 runs automatically (`test-business-capability` for non-CHANNEL,
  `test-app` for CHANNEL). Failure feeds back into the implementation agent
  via a `── REMEDIATION CONTEXT ──` block, bounded by `max_loops`.
- For non-CHANNEL Mode A, an optional **contract harness** is attached via
  `/harness-backend <CAP_ID>` — scaffolds a `*.Contracts.Harness/` project
  that derives `openapi.yaml` + `asyncapi.yaml` from the process model
  (`rlv-knowledge process <CAP_ID>`) and the BCM corpus, with bidirectional
  `x-lineage` extensions.

## Skill cheatsheet

| Command | What it does |
|---|---|
| `/implementation-pipeline` | Status across all capabilities; advance to next pending stage |
| `/process <CAP_ID>` | Stage 0 — interactive DDD modelling. **Lives in the `reliever-knowledge` repo**, not here; consumed here via `rlv-knowledge process <CAP_ID>` |
| `/sketch-miro` | Render every process-modelled capability (enumerated via `rlv-knowledge process --list`) as a Miro Event Storming board |
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
  from disk — they don't live here. Use `rlv-knowledge pack <CAP_ID> [--deep] [--compact]`
  for knowledge (`BNK.RLVR.…`), `tech pack <CAP_ID> …` for the platform
  substrate (`BNK.TECH.…`), and the `gov` CLI for organisation-wide governance
  ADRs (`banking-governance`). `<CAP_ID>` is always the **full source-context-prefixed
  ID**; the short `CAP.…` form is rejected (exit 2) by the v2.0.0 CLIs.
- **Provenance is recorded; drift is detected.** The `knowledge_base` block of
  `rlv-knowledge pack`/`version`/`process` (git ref + commit + date) is stamped by
  `/process` into the process model and carried forward as `bcm_ref` on TASK
  frontmatter. `/implementation-pipeline` and `/fix` run `rlv-knowledge diff <bcm_ref>
  --capability <CAP_ID>` to flag upstream changes since an artifact was generated.
- **The process model is upstream and read-only here.** It lives in
  `reliever-knowledge` (authored by `/process`) and is consumed via
  `rlv-knowledge process <CAP_ID>` — never read from a local `process/` folder (there
  is none) and never written. Stage-0 readiness is `rlv-knowledge process <CAP_ID>`
  returning exit 0; `/roadmap`, `/task`, `/launch-task`, `/code`, `/fix` refuse
  to run until the model resolves (i.e. its `/process` PR is merged upstream).
- **One authoring skill per folder.** `/roadmap` → `roadmap/`,
  `/task` → `tasks/<CAP_ID>/`, `/sort-task` → `tasks/BOARD.md`, `/code` → `sources/`
  and `src/`, the test skills → `tests/`, `/c4-export` → `docs/c4/`. No skill writes
  outside its lane. (`/process` and `process/` are owned by `reliever-knowledge`.)
- **Branch isolation is end-to-end.** One branch (`feat/TASK-NNN-{slug}`) and
  one worktree (`/tmp/kanban-worktrees/TASK-NNN-{slug}/`) per task. RabbitMQ
  exchanges/queues, ports, OTel `environment` tag, and frontend branch badge
  all carry the branch slug — concurrent worktrees never collide.
- **One `/code` agent per task; one active task per capability.**
- **Loop counters live on the TASK file**, not on the board.
- **Every artifact traces back** to a TASK → roadmap epic → process model →
  BCM capability (`BNK.RLVR.CAP.…`) → FUNC ADR → URBA constraints, pinned to a
  knowledge-base `bcm_ref`. The chain is unbreakable and version-anchored.

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

- New capability, never modelled → `/implementation-pipeline` (it will tell you
  to run `/process <CAP_ID>` **in the `reliever-knowledge` repo** first — until
  `rlv-knowledge process <CAP_ID>` resolves, there is nothing to plan against).
- Process model published (`rlv-knowledge process <CAP_ID>` exits 0), no roadmap yet → `/roadmap`.
- Roadmap merged, no tasks → `/task`.
- Tasks exist → `/launch-task` (or `/launch-task auto`).
- Something is red → `/fix` with the PR number, branch, or log paste.
