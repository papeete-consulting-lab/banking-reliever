---
name: roadmap
description: >
  Breaks a validated L2 or L3 business capability into an implementation roadmap expressed as 
  epics and milestones. Produces /roadmap/{capability-id}/roadmap.md for each capability. Use this 
  skill whenever the user wants to roadmap how to implement a capability, create an epic breakdown, 
  define milestones for a capability, or produce a capability roadmap. Trigger on: "roadmap this 
  capability", "create a roadmap", "epic breakdown", "roadmap for capability", "how do we implement 
  [capability]", "roadmap phase", or any time the BCM YAML exists and the user is ready to plan 
  implementation. Also trigger proactively after the BCM writer produces validated YAML for 
  a new capability.
---

# Roadmap Skill

You are producing an **implementation roadmap** for one or more business capabilities. The roadmap 
expresses what must be built (in business terms), in what order, with what dependencies — 
without specifying how it is built technically. The roadmap bridges the capability definition 
(from the BCM/ADRs + the `/process` Process Modelling layer) and the task generation phase.

**Absolute constraint**: No code, no technical architecture. The roadmap is in business capability 
language. The "how" emerges in the task phase.

---

## Process model — consumed read-only via `kpack process`

> The DDD process model (aggregates, commands, policies, read-models, bus
> topology, JSON Schemas) is authored by the `/process` skill in the
> **reliever-knowledge** repo and consumed here **read-only** via
> `kpack process <CAP_ID>` — exactly like the BCM corpus via `kpack pack`.
> It does not live in this repo, so there is nothing to guard locally and
> nothing to write under `process/`.

This skill consumes the model as a primary input to ground epics in real
aggregates and commands. Fetch it once via `kpack process <CAP_ID>` and read
the slices it returns; do not attempt to derive aggregates or commands inside the
roadmap, that is a category violation owned by `/process`.

---

## Readiness gate — the process model must resolve via `kpack process`

Before reading anything from the process model, verify it resolves. A model is
ready iff `kpack process <CAP_ID>` returns exit 0 (kpack resolves the
published `main` of reliever-knowledge by default).

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
CAP_ID="<CAPABILITY_ID>"

# The process model lives in reliever-knowledge now; it is ready iff kpack
# can resolve it (kpack resolves the published main by default).
if ! kpack process "$CAP_ID" --compact >/tmp/process-model.json 2>/tmp/process-model.err; then
  echo "GATE-FAIL: no process model for $CAP_ID."
  echo "Run /process $CAP_ID in the reliever-knowledge repo and merge its PR, then retry."
  cat /tmp/process-model.err
  exit 1
fi
```

If the gate fails, **stop and surface the failure to the user with the redirect
message above** — do not proceed to draft the roadmap. Once `/process <CAP_ID>`
is run in the reliever-knowledge repo and its PR merged, re-run `/roadmap`.

---

## Knowledge access — `kpack` CLI (mandatory)

**You MUST source all BCM, ADR, vision, and event knowledge from the `kpack` CLI.**
Do not read `/bcm/`, `/func-adr/`, `/adr/`, `/strategic-vision/`, `/product-vision/`, or any 
other knowledge file directly from the local working directory — those paths may be missing, 
stale, or incomplete in this checkout. The authoritative corpus lives in the
`Banking-PapeeteConsulting/reliever-knowledge` Git repository, and `kpack` is the only sanctioned 
way to query it.

Two subcommands are all you need:

```bash
# 1. Enumerate plannable capabilities (use to disambiguate user input)
kpack list --context BNK.RLVR --level L2
kpack list --context BNK.RLVR --level L3

# 2. Fetch the full pack for one capability (lightweight mode is the default)
kpack pack <CAPABILITY_ID> --deep --compact
```

Always pass `--deep` from this skill: it pulls in the rationale ADRs (URBA, governance,
tech-strategic) behind the `*-vision.md` narratives, which the roadmap needs for strategic 
alignment. Add `--compact` to keep the JSON on a single line — easier to pipe into `jq` or
`python3 -c`.

The pack JSON exposes these slices under `slices.*` — map them to the roadmap sections:

| Slice                       | What it gives you                                      | Roadmap section it feeds             |
|-----------------------------|--------------------------------------------------------|--------------------------------------|
| `capability_self`           | The L2/L3 itself (description, owner, ADRs)            | Capability Summary                   |
| `capability_ancestors`      | Parent L1 (and grandparent if L3)                      | Strategic Alignment                  |
| `capability_definition`     | The governing FUNC ADR(s)                              | Epic framing, Exit conditions        |
| `emitted_events[]` `\| select(.layer=="business")`   | Events the capability must produce            | Epics — "Unlocks events"             |
| `consumed_events[]` `\| select(.layer=="business")`  | Events the capability subscribes to           | Cross-capability dependencies        |
| `emitted_events[]` `\| select(.layer=="resource")`   | Technical projections of emitted events       | Sanity check on event topology       |
| `consumed_events[]` `\| select(.layer=="resource")`  | Technical subscriptions                       | Sanity check on event topology       |
| `carried_objects`           | Business objects owned/touched by the capability       | Capability Summary                   |
| `carried_concepts`          | Canonical business concepts with definition + rules    | Capability Summary, Open Questions   |
| `governance_adrs`           | Applicable GOV ADRs (review cycle, arbitration…)       | Risks, Sequencing constraints        |
| `governing_urba`            | URBA ADRs scoping this capability                      | Risks, Sequencing constraints        |
| `governing_tech_strat`      | Strategic-tech ADRs that frame the zone                | Strategic Alignment                  |
| `tactical_stack`            | Tactical-tech ADRs already accepted for this L2        | Strategic Alignment                  |
| `product_vision`            | Product-vision narrative + rationale (with `--deep`)   | Strategic Alignment, North-star      |
| `business_vision`           | Strategic-business narrative + rationale               | Strategic Alignment                  |
| `tech_vision`               | Strategic-tech narrative + rationale                   | Strategic Alignment                  |
| `vocab`                     | Allowed levels and zoning values                       | Validation only                      |

Always check `pack.warnings` after invocation — non-empty means the corpus has gaps that
should land in the roadmap's **Open Questions** section.

### Repo ref and offline behaviour

- Default ref is `main` on `git@github.com:Banking-PapeeteConsulting/reliever-knowledge.git`. To pin a 
  specific snapshot (e.g. matching a release): `kpack --ref v0.1.0 pack <ID> --deep --compact`.
- Cached locally under `~/.cache/kpack/`. Add `--no-fetch` to skip the per-invocation 
  `git fetch` if the network is slow or unreachable; `--fresh` re-clones from scratch.
- If the user has a local checkout, they can set `BANKING_KNOWLEDGE_ROOT=/path/to/checkout` 
  and `kpack` will read from disk silently. Don't assume that's the case.

### Recommended invocation pattern

```bash
# One JSON object → parse it once, then drive the roadmap from the parsed slices.
kpack pack BNK.RLVR.CAP.BSP.001.PAL --deep --compact > /tmp/pack.json
jq '.slices.capability_self[0]'                                  /tmp/pack.json
jq '.slices.capability_definition[0]'                           /tmp/pack.json
jq '[.slices.emitted_events[] | select(.layer=="business")]'    /tmp/pack.json
jq '.warnings'                                                  /tmp/pack.json
```

If the capability ID is unknown to `kpack pack` (exit code 2), do not fall back to local
files — surface the error to the user and ask them to confirm the ID against `kpack list --context BNK.RLVR`.

---

## Before You Begin

1. **Identify which capability to roadmap.** The user should specify the capability ID (e.g., 
   `BNK.RLVR.CAP.BSP.001.PAL`) or a name. If ambiguous, run `kpack list --context BNK.RLVR --level L2` (and 
   `--level L3` if relevant), present the matches, and ask the user to select.

2. **Fetch the capability pack** with `kpack pack <ID> --deep --compact`. This single call 
   replaces all of the previous local file reads (capability YAML, FUNC ADR, strategic 
   vision, product vision, etc.). Do not read those files from disk.

3. **Read the Process Modelling layer (read-only).** Fetch it once with
   `kpack process <CAPABILITY_ID> --compact` and read the slices from the
   returned envelope (use `.model.<stem>.parsed`, falling back to `.raw` when
   `parsed` is null). These are produced by the `/process` skill in
   reliever-knowledge and are the canonical source of:
   - the **aggregates** (consistency boundaries) the roadmap must deliver — `.model.aggregates`,
   - the **commands** the capability accepts — `.model.commands` (often `parsed:null`; use `.raw`),
   - the **policies** wiring consumed events to commands — `.model.policies`,
   - the **read-models** and queries the capability exposes — `.model["read-models"]` (often `parsed:null`; use `.raw`),
   - the **bus topology** (exchanges, routing keys, subscriptions) — `.model.bus`.

   If `kpack process` does not resolve (gate fail above), **stop** and ask the
   user to run `/process <CAPABILITY_ID>` in the reliever-knowledge repo and merge
   its PR. Do **not** attempt to invent aggregates / commands from the FUNC ADR —
   that is `/process`'s responsibility.

   If the model lacks an entry referenced in `pack.slices.emitted_events` /
   `pack.slices.consumed_events`, surface the gap and ask the user to refresh
   `/process` upstream.

4. **Check if a roadmap already exists** locally at `/roadmap/{capability-id}/roadmap.md`. This *is* a
   local file — the roadmap output lives in the working repo, not in `reliever-knowledge`. If it 
   exists, ask: "A roadmap already exists. Do you want to update it or start fresh?"

   The folder `/tasks/` is reserved for the kanban (`/tasks/BOARD.md` and the
   per-capability `/tasks/<CAP_ID>/TASK-*.md` cards) — the `/roadmap` skill writes
   only to `/roadmap/`, never to `/tasks/`.

---

## Planning Framework

A capability roadmap is organized around **epics** — coherent chunks of business functionality 
that can be delivered incrementally. An epic:
- Delivers a meaningful business outcome (not a technical deliverable)
- Has a clear start and end condition
- Can be estimated in relative complexity (Small / Medium / Large / XL)
- Has identifiable dependencies on other epics or external capabilities

### Epics, not features

Good epic: "Establish the credit risk scoring baseline — enable underwriters to receive and 
interpret a risk score for standard loan applications."

Bad epic: "Build the risk API" or "Set up the database schema"

Epics should be named and defined so that a business owner can understand what will be 
deliverable when it's done.

---

## Step 1 — Understand the Capability

Before drafting the roadmap, ground yourself in the pack's `capability_self`,
`capability_definition`, and the `emitted_events[] | select(.layer=="business")` slices, then ask the user to 
validate the framing:

- "Looking at [capability name], what is the minimum version of this capability that delivers 
  business value? What would be true about the business on day 1 if this capability existed 
  in its simplest form?"
- "Among the events listed in `emitted_events[] | select(.layer=="business")` ([list them]), which is the most 
  critical to deliver first?"
- "Are there external dependencies — capabilities that must exist or expose data before this 
  one can function? (Cross-check against `consumed_events[] | select(.layer=="business")`.)"

---

## Step 2 — Draft Epics

Based on the FUNC ADR (`capability_definition`), the BCM data (`capability_self`,
`carried_objects`, `carried_concepts`), and the answers above, draft a set of 3-8 epics. 
Present them as a numbered list with a one-line description each. Ask the user to react 
before filling in the details.

For each epic, define:
- **Name**: clear, business-language title
- **Goal**: one sentence — what business outcome does this epic achieve?
- **Entry condition**: what must be true / done / available before this epic can start?
- **Exit condition** (Definition of Done): what is verifiably true when this epic is complete?
- **Complexity**: S / M / L / XL (relative estimation — no days or sprints)
- **Capabilities needed**: which other L2 capabilities must exist or be partially ready?
  Source this from `(.slices.consumed_events[] | select(.layer=="business")).subscribed_event` (trace the event back to its
  emitting capability via another `kpack pack` call if needed).
- **Key business events unlocked**: which events from `emitted_events[] | select(.layer=="business")` become 
  producible when this epic is done?

Ask the user to validate the epic sequence before writing the file:
> "Here's my proposed epic sequence for [capability]. Does the ordering make sense? 
> Are there any missing epics, or any that seem out of order?"

---

## Step 3 — Risk and Dependencies

For the full roadmap, identify:
- **Cross-capability dependencies**: from `consumed_events[] | select(.layer=="business")` — which other L2s does 
  this roadmap depend on? (Reference by capability ID.)
- **External dependencies**: third-party systems, data sources, regulatory approvals
- **Key risks**: the 2-3 assumptions that, if wrong, would derail this roadmap. Cross-check 
  against `governance_adrs` and `governing_urba` for hard constraints.
- **Recommended sequencing constraint**: which epics are truly sequential vs. which could 
  be run in parallel?

---

## Sentinel — acquire before writing under `roadmap/`

The `roadmap/{capability-id}/` folder is owned by **this skill alone**. A
PreToolUse hook (`roadmap-folder-guard.py`) rejects every `Write`, `Edit`,
`MultiEdit`, and `NotebookEdit` call targeting `roadmap/**` unless the
session sentinel `/tmp/.claude-roadmap-skill.active` is present (and fresh,
i.e. touched within the last 30 minutes). This is what stops `/task`,
`/code`, `/fix`, `/launch-task`, `/continue-work`, and the agents they
spawn (`implement-capability`, `create-bff`, `code-web-frontend`,
`test-business-capability`, `test-app`) from drifting the roadmap as a
side-effect of an implementation loop.

**Before** writing the first byte under `roadmap/`, mark the session as a
`/roadmap` session by touching the sentinel file:

```bash
touch /tmp/.claude-roadmap-skill.active
```

The hook recognises both `<repo>/roadmap/...` and, if a worktree variant is
ever introduced, `/tmp/roadmap-worktrees/<CAP_ID>/roadmap/...` as guarded
paths, so the same sentinel covers both.

**At the very end** of the skill (success or graceful abort), remove it:

```bash
rm -f /tmp/.claude-roadmap-skill.active
```

If you abort mid-session because of a hard error or because the user stops
you, still attempt the `rm -f` in your final message. A stale sentinel
grants write access to the next agent — that is undesirable. The hook
treats sentinels older than 30 minutes as expired, but explicit cleanup is
preferred.

---

## Output

**File**: `/roadmap/{capability-id}/roadmap.md` (create directory if needed)

> Do NOT write under `/tasks/` — that folder is reserved for the kanban
> (`/tasks/BOARD.md` and `/tasks/<CAP_ID>/TASK-*.md` cards). The roadmap is a
> separate artefact with its own root.

**Format**:

```markdown
# Roadmap — [Capability Name] ([Capability ID])

## Capability Summary
> [One-sentence capability responsibility from `capability_self[0].description`]

## Strategic Alignment
- Service offer: [from `product_vision`]
- Strategic L1: [from `capability_ancestors[0]`]
- BCM Zone: [from `capability_self[0].zoning`]
- Governing FUNC ADR: [from `capability_definition[*].id`]
- Strategic-tech anchors: [from `governing_tech_strat[*].id` and `tactical_stack[*].id`]

## Implementation Epics

### Epic 1 — [Name]
**Goal**: [One sentence]
**Entry condition**: [What must be true to start]
**Exit condition**: [What is verifiably true when done]
**Complexity**: [S/M/L/XL]
**Unlocks events**: [list of business events this epic enables]
**Dependencies**: [Capability IDs or external systems]

### Epic 2 — [Name]
[Same structure]

...

## Dependency Map

| Epic | Depends On | Type |
|------|-----------|------|
| Epic 2 | Epic 1 | Sequential |
| Epic 3 | BNK.RLVR.CAP.REF.001 | Cross-capability |
...

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| [Risk] | H/M/L | H/M/L | [Mitigation] |

## Recommended Sequencing
[Short narrative: which epics are on the critical path, which can run in parallel]

## Open Questions
- [Any decision that must be made before a specific epic can start]
- [Anything surfaced via `pack.warnings`]

## Knowledge Source
- kpack ref: [the `--ref` used, default `main`]
- Capability pack mode: deep
- Pack date: [today's date]
```

After writing, release the sentinel:

```bash
rm -f /tmp/.claude-roadmap-skill.active
```

Then tell the user:
> "The roadmap for [capability] is committed to `/roadmap/[capability-id]/roadmap.md`. 
> When you're ready, the task skill will break each epic into concrete tasks for 
> the implement-capability agent (written under `/tasks/[capability-id]/`)."
