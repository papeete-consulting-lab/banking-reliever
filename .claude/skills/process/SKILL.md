---
name: process
description: >
  Generates the **Process Modelling** layer of a business capability — the DDD
  tactical layer that sits between Big-Picture Event Storming (BCM YAML, FUNC
  ADR, URBA/TECH-STRAT ADRs, product/business/tech visions consumed via
  `bcm-pack`) and Software Design (the `/roadmap` → `/task` → `/code` pipeline that
  consumes it). Produces `process/{capability-id}/` as a durable, re-plan-resistant
  set of YAML artifacts: aggregates, commands, policies, read-models, bus
  topology, derived REST surface, JSON Schemas. Use this skill whenever the
  user wants to model the process of a capability, sketch its aggregates and
  commands, decide its bus topology, capture its reactive policies, or generate
  command/event JSON Schemas. Trigger on: "process this capability", "process
  modelling", "process modeling", "model the process for X", "/process X",
  "aggregates and commands for X", "domain events for X", "Event Storming for
  X", "design the bus for X", "tactical DDD for X", "design the aggregates for
  X", or any time a BCM-validated capability is ready to be modelled before
  `/roadmap` runs. Also trigger proactively after `bcm-pack pack <CAP_ID>` returns a
  complete corpus and the user is about to start `/roadmap` — `/roadmap` should always
  read a `process/{capability-id}/` folder, never re-derive it.

  Authorship rule: `/process` is the **only** authority on `process/{capability-id}/`.
  No other skill — `/roadmap`, `/task`, `/code`, `/fix`, `/launch-task`, `/continue-work`
  — and no agent spawned by them (`implement-capability`, `create-bff`,
  `code-web-frontend`, `test-business-capability`, `test-app`) may modify any
  file under `process/`. PR / CI-CD branches opened by `/launch-task`, `/code`,
  or `/fix` must not include modifications under `process/{capability-id}/`. A
  `PreToolUse` hook (`process-folder-guard.py`) enforces this: Write / Edit /
  MultiEdit / NotebookEdit calls targeting any path under `process/` are
  rejected unless the `/process` skill's session sentinel
  (`/tmp/.claude-process-skill.active`) is present.

  Publication rule: `/process` always works on a dedicated branch
  `process/<CAP_ID>` inside an isolated worktree at
  `/tmp/process-worktrees/<CAP_ID>/`. It commits, pushes, and opens (or
  refreshes) a Pull Request titled `process(<CAP_ID>): …` against `main`.
  The PR must be reviewed and merged before any downstream skill (`/roadmap`,
  `/task`, `/launch-task`, `/code`, `/fix`) can consume the model on `main`
  — those skills enforce a readiness gate that refuses to run when the
  capability has either no `process/<CAP_ID>/` on `main` or an open
  unmerged process PR.

  Upstream readiness rule: `/process` refuses to run unless **at least one
  tactical tech ADR (`ADR-TECH-TACT-*`) scopes the capability** — i.e. the
  `tactical_stack` slice returned by `bcm-pack pack <CAP_ID> --deep` is
  non-empty. Tactical tech ADRs are the bridge between TECH-STRAT (zone-wide
  rules) and the tactical DDD model produced here; without one, there is no
  ratified per-capability stack decision to ground aggregate / bus / schema
  choices on. The skill aborts before creating the branch / worktree in that
  case and sends the user upstream to author the ADR in `banking-knowledge`.
---

# Process — Tactical DDD Process Modelling

You are running an **Event-Storming-style modelling session** for one business
capability and committing the result as a durable model under
`process/{capability-id}/`. This layer is what every downstream skill (`/roadmap`,
`/task`, `/code`, `/fix`, `/launch-task`) reads to know what aggregates exist,
what commands they accept, what policies wire consumed events to commands, what
read-models project the domain events, and what bus topology the capability
publishes / subscribes to.

The output is **architecture-neutral** within the strategic-tech corridor:
.NET / Clean Architecture / DDD on RabbitMQ + MongoDB is assumed (per
`ADR-TECH-STRAT-001`), but the YAML deliberately does not name C# classes,
`MassTransit` consumers, or Mongo collections. That is the `implement-capability`
agent's job downstream.

> **Position in the pipeline.** `/process` runs **after** `bcm-pack` has a
> complete corpus for the capability and **before** `/roadmap`. The skill chain is
> now: `bcm-pack pack <CAP_ID> --deep` → **`/process <CAP_ID>`** → `/roadmap` →
> `/task` → `/launch-task` → `/code` → `/test-business-capability` or
> `/test-app`. `/roadmap` no longer derives aggregates/commands itself — it reads
> them from this folder.

---

## Readiness gates (run before Step 0)

Two upstream conditions must hold before this skill is allowed to create the
branch / worktree and start writing. Check them in this order; if either
fails, abort with a clear message and do **not** touch the filesystem or
network. No worktree, no sentinel, no commit — the user must fix the gap in
`banking-knowledge` first.

1. **BCM corpus is complete for `<CAP_ID>`.** `bcm-pack pack <CAP_ID> --deep`
   returns `warnings: []` and every required structural slice
   (`capability_self`, `capability_definition`, `emitted_resource_events`,
   `carried_objects`, `governing_urba`, `governing_tech_strat`) is non-empty.
2. **At least one tactical tech ADR scopes the capability.** The
   `tactical_stack` slice contains ≥ 1 ADR. Each item has
   `family: TECH`, `tech_domain: TACTICAL_STACK`, an `id` matching
   `ADR-TECH-TACT-*`, and a `capability_id` equal to `<CAP_ID>`. Empty list
   ⇒ abort.

The second gate is hard. Tactical tech ADRs ratify the per-capability stack
choices that this skill's YAML output materialises (event-store flavour,
outbox / snapshotting / projection strategy, schema-evolution policy, …).
Without one, `/process` would invent those decisions silently — which is
exactly the failure mode the ADR system exists to prevent.

Concrete gate (implemented in **Step 0.1.b** below — runs after capability
resolution at Step 0.1 and before Step 0.2 creates the worktree; this
section restates the logic so the rule is visible up-front):

```bash
bcm-pack pack "$CAP_ID" --deep --compact > /tmp/pack-process.json

# Gate 1 — corpus completeness
WARN_COUNT=$(jq '.warnings | length'                              /tmp/pack-process.json)
HAS_SELF=$(jq    '.slices.capability_self        | length > 0'    /tmp/pack-process.json)
HAS_DEF=$(jq     '.slices.capability_definition  | length > 0'    /tmp/pack-process.json)
HAS_RVT=$(jq     '.slices.emitted_resource_events| length > 0'    /tmp/pack-process.json)
HAS_OBJ=$(jq     '.slices.carried_objects        | length > 0'    /tmp/pack-process.json)
HAS_URBA=$(jq    '.slices.governing_urba         | length > 0'    /tmp/pack-process.json)
HAS_STRAT=$(jq   '.slices.governing_tech_strat   | length > 0'    /tmp/pack-process.json)

# Gate 2 — tactical tech ADR scopes this capability
TACT_COUNT=$(jq --arg cap "$CAP_ID" '
  [.slices.tactical_stack[]
    | select(.family == "TECH"
             and .tech_domain == "TACTICAL_STACK"
             and .capability_id == $cap)] | length
' /tmp/pack-process.json)

if [ "$TACT_COUNT" -eq 0 ]; then
  echo "✗ No tactical tech ADR scopes $CAP_ID."
  echo "  /process refuses to run. Author an ADR-TECH-TACT-* in banking-knowledge first."
  exit 1
fi
```

If either gate fails, stop here. Tell the user *which* gate failed and
*what* to author upstream (corpus fix, FUNC ADR completion, or a new
`ADR-TECH-TACT-*` scoped to this capability). Do not proceed to Step 0.

---

## Authorship rule (hard constraint)

- This skill is the **only writer** of `process/{capability-id}/`. The path is
  also protected by the `process-folder-guard.py` PreToolUse hook, which
  blocks every `Write` / `Edit` / `MultiEdit` / `NotebookEdit` call targeting
  `process/**` unless the session sentinel
  `/tmp/.claude-process-skill.active` is present. The hook does **not** parse
  Bash commands, so always use `Write` / `Edit` for files under `process/` —
  never shell redirects (`cat > …`, `sed -i`, `tee`, etc.).
- The hook recognises three roots as `process/**`:
  `<repo>/process/`, `/tmp/kanban-worktrees/TASK-NNN-*/process/`, and
  `/tmp/process-worktrees/<CAP_ID>/process/` — the last one being where this
  skill performs every write.
- All downstream skills and the agents they spawn treat `process/{capability-id}/`
  as **read-only**. Their PRs must never carry diffs under that path.
- `/process` is **idempotent and durable**: re-running it on an existing
  `process/{capability-id}/` is allowed (and expected when the FUNC ADR
  evolves), but it must always offer to diff first and ask before overwriting.

## Publication rule (hard constraint)

- `/process` writes nothing on the main checkout. Every modification happens
  inside a dedicated worktree at `/tmp/process-worktrees/<CAP_ID>/` checked
  out on a dedicated branch `process/<CAP_ID>`.
- At the end of the session, the skill commits the changes, pushes the
  branch, and opens (or refreshes) a Pull Request against `main`. The PR
  title is `process(<CAP_ID>): <one-line summary>` and the body recapitulates
  the modelling session (aggregates / commands / policies / read-models /
  bus topology decisions, plus open questions).
- The PR must be reviewed and merged through GitHub before any downstream
  skill (`/roadmap`, `/task`, `/launch-task`, `/code`, `/fix`) can consume the
  model on `main`. Those skills enforce a readiness gate (see "Readiness
  gate" section in each downstream SKILL.md).
- Re-running `/process <CAP_ID>` while the branch and worktree already exist
  is the supported refinement workflow: the skill reuses both, appends a
  new commit, and pushes. The existing open PR is updated in place — no new
  PR is opened.

---

## Step 0 — Branch, Worktree, and Sentinel

This skill **never writes on the main checkout**. It always runs inside a
dedicated git worktree on a dedicated branch, so the result can flow through
a normal Pull Request review before landing on `main`.

### 0.1 — Resolve paths

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
CAP_ID="<CAPABILITY_ID>"                              # e.g. BNK.RLVR.CAP.BSP.001.SCO
BRANCH_NAME="process/${CAP_ID}"
WORKTREE_PATH="/tmp/process-worktrees/${CAP_ID}"
```

### 0.1.b — Enforce the readiness gates (mandatory)

Run the two readiness gates from the "Readiness gates" section above
**before** creating the branch or the worktree. Pull the deep pack once
and reuse it for the rest of the session:

```bash
bcm-pack pack "$CAP_ID" --deep --compact > /tmp/pack-process.json

TACT_COUNT=$(jq --arg cap "$CAP_ID" '
  [.slices.tactical_stack[]
    | select(.family == "TECH"
             and .tech_domain == "TACTICAL_STACK"
             and .capability_id == $cap)] | length
' /tmp/pack-process.json)

if [ "$TACT_COUNT" -eq 0 ]; then
  echo "✗ /process refuses to run: no ADR-TECH-TACT-* scopes $CAP_ID."
  echo "  Author one in banking-knowledge (family=TECH, tech_domain=TACTICAL_STACK,"
  echo "  capability_id=$CAP_ID), publish it, then retry."
  exit 1
fi

jq --arg cap "$CAP_ID" '
  [.slices.tactical_stack[]
    | select(.capability_id == $cap)
    | { id, title, status, date }]
' /tmp/pack-process.json
```

If `TACT_COUNT == 0`, **stop here**: announce the failure to the user, point
them at the upstream `banking-knowledge` repo to author an
`ADR-TECH-TACT-*` scoped to this capability, and exit. Do **not** create the
worktree, do **not** touch the sentinel, do **not** open any PR. The
filesystem and the network must be untouched after this abort.

Also re-run the corpus-completeness checks (`warnings == []`, required
slices non-empty) and abort with an equally explicit message if any fail.

### 0.2 — Create or reuse the branch + worktree

```bash
mkdir -p /tmp/process-worktrees

if git -C "$PROJECT_ROOT" worktree list --porcelain \
      | grep -q "^worktree $WORKTREE_PATH\$"; then
  # Re-run on an existing /process session — reuse in place.
  echo "Reusing existing worktree at $WORKTREE_PATH on branch $BRANCH_NAME"
elif git -C "$PROJECT_ROOT" show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
  # Branch exists but no worktree — re-attach.
  git -C "$PROJECT_ROOT" worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
else
  # Greenfield — create branch off main and worktree in one shot.
  git -C "$PROJECT_ROOT" fetch origin main --quiet || true
  git -C "$PROJECT_ROOT" worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" main
fi
```

If the branch already exists and is behind `main`, fast-forward it before
working — this avoids opening a PR with stale baseline:

```bash
git -C "$WORKTREE_PATH" fetch origin main --quiet || true
git -C "$WORKTREE_PATH" merge --ff-only origin/main 2>/dev/null || true
```

**From this step onward, every `Write`, `Edit`, `Read`, `Bash`, and
`git diff` call MUST target paths under `$WORKTREE_PATH`.** Do not touch the
main checkout's `process/` tree — the readiness gate downstream depends on
`process/<CAP_ID>/` only appearing on `main` when the PR is merged.

### 0.3 — Sentinel

**Before** writing the first byte under `process/`, mark the session as a
`/process` session by touching the sentinel file:

```bash
touch /tmp/.claude-process-skill.active
```

This grants the `process-folder-guard.py` hook permission to allow `Write`,
`Edit`, `MultiEdit`, and `NotebookEdit` calls on `process/**` for the duration
of this skill invocation. The hook recognises both
`<repo>/process/...` and `/tmp/process-worktrees/<CAP_ID>/process/...` as
guarded paths, so the sentinel covers both.

**At the very end** of the skill (success or graceful abort), remove it:

```bash
rm -f /tmp/.claude-process-skill.active
```

If you abort mid-session because of a hard error or because the user stops
you, still attempt the `rm -f` in your final message. A stale sentinel grants
write access to the next agent — that is undesirable. The hook treats sentinels
older than 30 minutes as expired, but explicit cleanup is preferred.

---

## Step 1 — Identify the Capability and Inspect the Knowledge Pack

The user gives a capability ID (e.g. `BNK.RLVR.CAP.BSP.001.SCO`) or a name. If
ambiguous, run `bcm-pack list --level L2` (and `--level L3` if relevant) and
ask them to pick. Capability resolution must happen *before* Step 0.1.b
because the readiness gates need a concrete `$CAP_ID`.

The deep pack has already been pulled to `/tmp/pack-process.json` by Step
0.1.b (the readiness gate). Reuse that file — do **not** re-invoke
`bcm-pack`. Walk the slices that drive each artefact:

```bash
jq '.warnings'                            /tmp/pack-process.json
jq '.slices.capability_self[0]'           /tmp/pack-process.json
jq '.slices.capability_definition'        /tmp/pack-process.json
jq '.slices.emitted_business_events'      /tmp/pack-process.json
jq '.slices.emitted_resource_events'      /tmp/pack-process.json
jq '.slices.consumed_business_events'     /tmp/pack-process.json
jq '.slices.consumed_resource_events'     /tmp/pack-process.json
jq '.slices.carried_objects'              /tmp/pack-process.json
jq '.slices.carried_concepts'             /tmp/pack-process.json
jq '.slices.governing_urba'               /tmp/pack-process.json
jq '.slices.governing_tech_strat'         /tmp/pack-process.json
jq '.slices.tactical_stack'               /tmp/pack-process.json
```

Slice → process artefact mapping:

| Slice                       | Drives                                                 |
|-----------------------------|--------------------------------------------------------|
| `capability_self`           | `meta.capability`, target zone, level, owner           |
| `capability_definition`     | Aggregates, invariants, commands, policy intent — the FUNC ADR is the primary source of behaviour |
| `emitted_business_events`   | Paired EVT names on the routing keys (`bus.yaml`)      |
| `emitted_resource_events`   | RVT names emitted by aggregates (`aggregates.yaml`, `bus.yaml`) |
| `consumed_business_events`  | `policies.yaml` listens-to entries, business-subscriptions |
| `consumed_resource_events`  | `policies.yaml` resource-subscriptions, queue bindings |
| `carried_objects`           | `OBJ.*` references on aggregates (`aggregates.yaml`)   |
| `carried_concepts`          | Vocabulary grounding for command intents and errors    |
| `governing_urba`            | Naming, event meta-model, identifier conventions       |
| `governing_tech_strat`      | Bus topology rules (`bus.yaml`) — `ADR-TECH-STRAT-001` is normative |
| `tactical_stack` **(required — gate)** | Per-capability `ADR-TECH-TACT-*` ratifying the stack choices this model materialises (event-store flavour, outbox / snapshotting / projection strategy, schema-evolution policy). **Empty list ⇒ `/process` aborts at Step 0.1.b.** |

If `pack.warnings` is non-empty, or any required slice is empty, or
`tactical_stack` has no entry scoping `$CAP_ID`, **stop** — `/process` cannot
run on an incomplete corpus. The first two failures point at the BCM / FUNC
ADR; the third points at a missing `ADR-TECH-TACT-*`. In every case send
the user upstream to `banking-knowledge` to author or complete the artefact
before retrying.

---

## Step 2 — Detect Existing Process Folder (idempotency)

Look in **both** the worktree (where prior work-in-progress on this branch
lives) and on `main` (the merged baseline):

```bash
ls "$WORKTREE_PATH/process/$CAP_ID/"             2>/dev/null    # WIP on this branch
git -C "$PROJECT_ROOT" ls-tree --name-only main -- "process/$CAP_ID" 2>/dev/null   # merged baseline
```

| State                                                               | Action                                                                                          |
|---------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| Folder absent on main AND on branch                                 | Greenfield modelling.                                                                           |
| Folder present on main, FUNC ADR unchanged                          | Ask the user: "A merged process model exists. Do you want to refine it, regenerate, or stop?"   |
| Folder present on main, FUNC ADR has new events                     | Run a *delta* session — keep stable AGG/CMD/POL identifiers, append new commands / events / policies. Never silently rename existing IDs (downstream code is keyed on them). |
| Folder present only on branch (prior `/process` run, PR still open) | Resume in place — the previous diff is still under review. Append refinements as a new commit on the same branch; the open PR is updated by the push in Step 6.5. |

Always show a `git diff` of any change before writing the final files, so the
user can sanity-check the delta. All `git diff` calls run inside the
worktree: `git -C "$WORKTREE_PATH" diff -- process/$CAP_ID/`.

---

## Step 3 — Run the Modelling Session

A capability process model is built from six interlocking views. Walk the user
through them in this order, surfacing one decision at a time and writing
nothing until each view is validated.

### 3.1 Aggregates (`aggregates.yaml`)

Start with the question: *"What pieces of state need their own consistency
boundary? Which business object does each protect?"*

For each aggregate, capture:

- `id`: `AGG.<ZONE>.<L1>.<L2>.<NAME>` (kebab-screamcase)
- `name`: human-readable
- `business_object`: `OBJ.*` reference (must exist in the `carried_objects` slice)
- `aggregate_id_field` and cardinality
- `state` fields with their kind (`identity`, `snapshot`, `idempotency`,
  `configuration`, `read-through`)
- `accepted_commands` — forward-references commands defined in 3.2
- `emitted_resource_events` — must each appear in `emitted_resource_events`
  from `bcm-pack` (or be flagged as an Open Question)
- `invariants` — business rules enforced atomically inside the aggregate.
  Each invariant has an `id` (`INV.<L2>.NNN`), a `rule`, a `rationale`
  (cite the FUNC/URBA/TECH-STRAT ADR), and optionally an `open_question`.
- `consistency_boundary`, `transactional_outbox`, `snapshotting`

Key questions to resolve at this view:

- **Granularity.** One aggregate per `<entity_id>`? Per `(<entity_id>,
  <variant>)`? Justify and record the alternative as an open question.
- **Atomicity of conditional events.** When a command may emit a primary
  event *and* a conditional secondary one (e.g. threshold crossing), is it
  atomic in the aggregate or delegated to a downstream observer? This
  decision belongs to the aggregate invariants, not to the command.
- **Idempotency.** What replay key does each command use? Is the window
  bounded (e.g. `30d`) or lifetime (e.g. one-shot baseline)?

### 3.2 Commands (`commands.yaml`)

For each verb the capability accepts:

- `id`: `CMD.<ZONE>.<L1>.<L2>.<VERB>`
- `name`, `intent` (one-paragraph business statement)
- `accepted_by`: exactly one `AGG.*`
- `issued_by`: list of `POL.*` (defined in 3.3) + optionally an HTTP/API caller
- `payload_schema`: relative path under `schemas/`
- `preconditions`: numbered `PRE.NNN`
- `invariants_enforced`: cross-references the `INV.*` from 3.1
- `emits`: `RVT.*` (and optionally a comment naming the paired `EVT.*`
  business-event family — per `ADR-TECH-STRAT-001` Rule 2, only resource
  events are autonomous bus messages; business events appear only in routing
  keys per Rule 4)
- `errors`: `code` + `when`
- `idempotency`: `key` + `window`
- `api_binding`: `{method, path}` — feeds `api.yaml`

### 3.3 Policies (`policies.yaml`)

A policy listens to one or more (resource) events and issues a command.
Aggregates never subscribe to events directly.

For each policy:

- `id`: `POL.<ZONE>.<L1>.<L2>.<NAME>`
- `name`, `intent`
- `listens_to` — for each entry: `resource_event`, `business_subscription`,
  `resource_subscription`, optional `trigger_kind`
- `issues` — exactly one `CMD.*`
- `mapping_rule` — how the upstream payload becomes the command payload
- `error_handling` — per error code from the issued command:
  `ack-and-drop`, `retry`, `dlq`, with rationale
- `delivery` — `at-least-once` (default) or `exactly-once` (rare; justify)

If a policy currently has no upstream event because the upstream FUNC ADR
isn't ready, set `status: placeholder` and add an `open_question` describing
the missing upstream signal.

### 3.4 Read-models and queries (`read-models.yaml`)

For each projection:

- `id`: `PRJ.<ZONE>.<L1>.<L2>.<NAME>`
- `backs_resource` (optional; the `RES.*` it projects)
- `fed_by` — list of `RVT.*`
- `fields` — denormalised columns
- `consistency` — `eventual` (default) or `strong` (justify)
- `retention` — for history-style projections

Then declare the queries on top:

- `id`: `QRY.<ZONE>.<L1>.<L2>.<NAME>`
- `served_by` — exactly one `PRJ.*`
- `request` and `response` shape
- `consumers` — list of capability IDs (cross-check with the BCM
  `business-subscription` chain)
- `api_binding` and optional `cache: { etag, max_age }`

### 3.5 Bus topology (`bus.yaml`)

Apply `ADR-TECH-STRAT-001` rigorously — this view is normative:

- `publication`:
  - `broker: rabbitmq`
  - `exchange.name`: `<zone>.<l1>.<l2>-events` (lowercase, dot-separated, per
    Rule 1 / 5)
  - `exchange.type: topic`, `durable: true`, `owned_by: <CAPABILITY_ID>`
- `routing_keys` — one per emitted `RVT.*`. The routing key MUST be
  `<EVT-id>.<RVT-id>` (Rule 4). Only `RVT.*` are autonomous messages — never
  declare a standalone `EVT.*` message (Rule 2).
- `correlation_key` — typically the aggregate's identity field
- `identity_resolution` — explicit: do we ship the canonical referential ID,
  or do consumers resolve via a lookup?
- `subscriptions` — for every entry from `consumed_business_events` /
  `consumed_resource_events`: `source_capability`, `source_exchange`,
  `binding_pattern` (`<EVT>.<RVT>` form), declared `queue` name (must be
  prefixed with the consuming capability's exchange root: e.g.
  `<l1>.<l2>.q.<topic>`), and the consuming `POL.*`
- `consumers` — known downstream capabilities, with binding pattern and
  rationale (sourced from BCM `business-subscription` chain)

### 3.6 API surface (`api.yaml`) — derived

Synthesise from the `api_binding` fields declared in 3.2 and 3.4. This file
is **derived** but committed (so the `create-bff` and `implement-capability`
agents can consume one file instead of cross-walking two). Add a `meta.derivation`
note pointing at `commands.yaml` + `read-models.yaml`.

For each command: `operation_id`, `method`, `path`, `issues`, `request_schema`,
`responses` (with mapped error codes).
For each query: `operation_id`, `method`, `path`, `serves`, optional
`query_params`, `responses`.

### 3.7 JSON Schemas (`schemas/`)

For every command and event referenced in `commands.yaml` or `bus.yaml`, write
a JSON Schema:

- `schemas/CMD.<…>.<VERB>.schema.json` — command request payload
  (command IDs are **process-authored / capability-local** — no source-context prefix)
- `schemas/BNK.RLVR.RVT.<…>.<RESOURCE_EVENT>.schema.json` — resource-event
  payload. Resource-event IDs are **bcm assets**: carry the full source-context
  prefix (`BNK.RLVR.RVT.…`) returned verbatim by `bcm-pack`. The file name
  mirrors the full asset ID.

Use Draft 2020-12 (`"$schema": "https://json-schema.org/draft/2020-12/schema"`).
Each schema has a stable `$id` derived from the identifier, `additionalProperties: false`
on object types, and a `description` referencing the originating CMD or RVT.

Reuse common shapes (e.g. `case_id`, `event_id`, `timestamp`, `model_version`)
via local `$defs` rather than duplicating them across files.

> **Asset-ID namespacing (CLI v1.0.0+).** Every ID `bcm-pack` returns —
> `CAP/RVT/EVT/OBJ/SUB/RES/CON` — is **source-context-prefixed** (`BNK.RLVR.…`).
> Use those IDs **verbatim** in `bus.yaml` (routing keys, `binding_pattern`,
> `emits`, `fed_by`), `read-models.yaml`, schema file names and `$id`s. The
> routing-key form `<EVT-id>.<RVT-id>` therefore composes two already-prefixed
> IDs, e.g.
> `BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED.BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED`.
> **Process-authored tactical IDs** you invent here — `AGG/CMD/POL/PRJ/QRY` —
> are capability-local and stay **unprefixed**.

---

## Step 4 — Write the README

`process/<CAPABILITY_ID>/README.md` is the human entry point. It contains:

1. **One-paragraph framing** — what this folder *is* (Process Modelling layer)
   and what it is *not* (a plan, a milestone breakdown, an implementation).
2. **Upstream knowledge consumed** — list the `bcm-pack` slices that are
   canonical (BCM YAML, FUNC ADR, URBA, TECH-STRAT) so a reader knows where to
   look for the data this folder doesn't restate.
3. **Files in this folder** — one-line summary per `*.yaml` (mirror the table
   in this skill).
4. **Scenario walkthrough** — at least two end-to-end flows expressed as ASCII
   diagrams that walk an *event* → *policy* → *command* → *aggregate* → *event*
   chain. This is the part that lets a reviewer understand the model in two
   minutes without reading every YAML.
5. **Open process-level questions** — every decision flagged
   `open_question` in the YAMLs is repeated here, with the alternatives and
   the trade-off. These must be resolved (or accepted as known limitations)
   before `/code` runs.
6. **Governance** — the ADRs that govern the model (FUNC, URBA, TECH-STRAT)
   with one line each on their role.

Use the existing `process/BNK.RLVR.CAP.BSP.001.SCO/README.md` as the canonical example
of tone, depth, and structure.

---

## Step 5 — Validate Coherence Before Writing

Before committing files, mentally check (and announce to the user) the
following invariants. If any fail, fix the model — do not just write it.

1. **Closure of references.** Every `accepted_commands` entry on an aggregate
   exists in `commands.yaml`; every `issues` in a policy exists in
   `commands.yaml`; every `served_by` in a query exists in `read-models.yaml`;
   every `RVT.*` in `bus.yaml` is `emitted_resource_events` of exactly one
   aggregate.
2. **BCM closure.** Every `RVT.*` in `bus.yaml.routing_keys` appears in the
   `emitted_resource_events` slice of `bcm-pack`. Every consumed
   `binding_pattern` corresponds to an entry in `consumed_resource_events`.
   Mismatches mean either the BCM is incomplete (stop, send upstream) or the
   process model invented an event (forbidden).
3. **Single-aggregate-per-command.** No `CMD.*` is `accepted_by` more than
   one aggregate.
4. **Routing-key form.** Every routing key matches `<EVT-id>.<RVT-id>`
   (Rule 4 of `ADR-TECH-STRAT-001`).
5. **Schema coverage.** Every `CMD.*.payload_schema` and every
   `bus.yaml.routing_keys[*].schema` resolves to an actual file under
   `schemas/`.
6. **No bare `EVT.*` messages.** No standalone `EVT.*` autonomous bus message
   anywhere (Rule 2 of `ADR-TECH-STRAT-001`).

Announce: "Coherence checks ✅ — writing files." Then proceed.

---

## Step 6 — Write the Files

Write to `$WORKTREE_PATH/process/<CAPABILITY_ID>/`:

- `README.md`
- `aggregates.yaml`
- `commands.yaml`
- `policies.yaml`
- `read-models.yaml`
- `bus.yaml`
- `api.yaml`
- `schemas/CMD.*.schema.json` (one per command)
- `schemas/BNK.RLVR.RVT.*.schema.json` (one per emitted resource event)
- `.bcm-provenance.json` — **knowledge-base provenance stamp** (see Step 6.1)

Always use the `Write` and `Edit` tools — never shell redirects. The
`process-folder-guard.py` hook allows these calls because the sentinel from
Step 0.3 is in place AND the worktree path is recognised as a `process/**`
root.

Pass the **full absolute path** to the tools (e.g.
`/tmp/process-worktrees/BNK.RLVR.CAP.BSP.001.SCO/process/BNK.RLVR.CAP.BSP.001.SCO/aggregates.yaml`).
Never write to the equivalent path under the main checkout.

After every write, show the diff using
`git -C "$WORKTREE_PATH" diff -- process/$CAP_ID/<file>` before moving on.
This makes the modelling session reviewable in real time.

### Step 6.1 — Stamp the knowledge-base provenance

The Process Modelling layer is derived from a **specific version** of the
knowledge base. Capture that version so every downstream stage can detect when
upstream knowledge has moved since the model was authored (`bcm-pack diff`).

Capture the `knowledge_base` block — it is already embedded at the top of the
`bcm-pack pack` payload you fetched in Step 0, or fetch it standalone:

```bash
bcm-pack version --compact > "$WORKTREE_PATH/process/$CAP_ID/.bcm-provenance.json"
```

Write `.bcm-provenance.json` (via the `Write` tool, inside the worktree) with
the shape:

```json
{
  "capability_id": "BNK.RLVR.CAP.BSP.001.SCO",
  "generated_by": "/process",
  "knowledge_base": {
    "package_version": "1.0.0",
    "ref": "v1.0.0-1-gb06a4af",
    "commit": "b06a4af…",
    "committed_at": "2026-05-21T13:57:08+02:00",
    "dirty": false
  }
}
```

If `knowledge_base.dirty` is `true`, **stop and warn the user**: the model would
not be reproducible from a tagged ref. Mirror the `ref` + `committed_at` in the
README "Upstream knowledge consumed" section so a human reader sees the version
without opening the JSON. `/task` reads this file and copies `knowledge_base.ref`
into each TASK's `bcm_ref` frontmatter field.

---

## Step 6.5 — Commit, Push, and Open / Refresh the PR

Once all files have been written and the user has signed off on the diff:

### 6.5.1 — Stage and commit (inside the worktree)

```bash
cd "$WORKTREE_PATH"
git add "process/$CAP_ID/"
git status --porcelain
```

If `git status --porcelain` is empty, there is nothing to publish — skip
straight to Step 7. Otherwise, commit with a message that mirrors the
session:

```bash
git commit -m "$(cat <<'EOF'
process(<CAP_ID>): <one-line summary of the modelling decision>

- Aggregates: <list>
- Commands: <list>
- Policies: <list>
- Read-models: <list>
- Bus exchange: <name>
- Open questions: <count>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

If this is a *refinement* commit on an existing branch, prefix the subject
with `process(<CAP_ID>): refine — …` so the commit history reads cleanly.

### 6.5.2 — Push the branch

```bash
git push -u origin "$BRANCH_NAME"
```

### 6.5.3 — Open or refresh the PR

Detect whether a PR is already open for this branch:

```bash
PR_NUMBER=$(gh pr list --head "$BRANCH_NAME" --state open --json number --jq '.[0].number')
```

- **No open PR** — open one:

  ```bash
  gh pr create \
    --base main \
    --head "$BRANCH_NAME" \
    --title "process(<CAP_ID>): <one-line summary>" \
    --body "$(cat <<'EOF'
  ## Summary
  Process Modelling layer for `<CAP_ID>` — DDD tactical model produced by `/process`.

  ## Files
  - `process/<CAP_ID>/README.md`
  - `process/<CAP_ID>/aggregates.yaml`
  - `process/<CAP_ID>/commands.yaml`
  - `process/<CAP_ID>/policies.yaml`
  - `process/<CAP_ID>/read-models.yaml`
  - `process/<CAP_ID>/bus.yaml`
  - `process/<CAP_ID>/api.yaml`
  - `process/<CAP_ID>/schemas/*.json`

  ## Modelling decisions
  <copy the README's "Scenario walkthrough" section>

  ## Open questions
  <copy the README's "Open process-level questions" section>

  ## Downstream impact
  Once merged, `/roadmap <CAP_ID>` becomes runnable. Until then the readiness
  gate in `/roadmap`, `/task`, `/launch-task`, `/code`, and `/fix` will refuse
  to consume this capability.

  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  EOF
  )"
  ```

- **PR already open** — the `git push` above already updated it. Just
  resurface the URL:

  ```bash
  gh pr view "$PR_NUMBER" --json url --jq '.url'
  ```

Capture the URL of the (new or existing) PR for the final announcement.

---

## Step 7 — Tear Down the Sentinel and Announce

```bash
rm -f /tmp/.claude-process-skill.active
```

Then announce:

> "Process model for `<CAPABILITY_ID>` is committed on branch
> `process/<CAPABILITY_ID>` (worktree: `/tmp/process-worktrees/<CAP_ID>/`)
> and published as PR <PR_URL>. The PR must be reviewed and merged into
> `main` before any downstream skill can consume the model.
>
> While the PR is open:
> - `/roadmap`, `/task`, `/launch-task`, `/code`, and `/fix` will refuse to
>   run on this capability (readiness gate).
> - To refine the model, re-run `/process <CAPABILITY_ID>` — this skill
>   will reuse the existing branch and worktree and append a new commit
>   to the same PR.
>
> After merge:
> - The worktree at `/tmp/process-worktrees/<CAP_ID>/` can be removed with
>   `git worktree remove /tmp/process-worktrees/<CAP_ID> --force` (the user
>   does this — this skill never deletes a worktree it might still need).
> - `/roadmap <CAPABILITY_ID>` becomes runnable."

---

## Important Boundaries

- **No code, no test files, no implementation choices.** This skill stays at
  the tactical-DDD modelling layer. Class names, namespaces, MongoDB
  collections, MassTransit consumers, JSON-on-wire envelopes — those belong
  to the `implement-capability` and `create-bff` agents. The `*.schema.json`
  files in `schemas/` describe wire contracts, not implementation classes.
- **No new ADRs.** If the modelling session uncovers a decision that is
  bigger than the capability (a new naming convention, a new bus rule, a new
  zoning rule), stop and tell the user to author an ADR upstream in
  `banking-knowledge` first. Do not write the decision into a YAML and hope.
- **Never rename a stable identifier.** AGG / CMD / POL / PRJ / QRY ids are
  contracts. Once committed and consumed by `/roadmap`, `/task`, or `/code`,
  they cannot be renamed without a coordinated change across consumers. If a
  rename is unavoidable, treat it as a deprecation: add the new id, mark the
  old one `deprecated: true` with a `replaced_by`, and surface the migration
  in the README.
- **Sentinel discipline.** Always remove `/tmp/.claude-process-skill.active`
  on exit, even on aborts. The hook treats sentinels older than 30 minutes as
  expired, but explicit cleanup is the right hygiene.
