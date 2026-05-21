# Process Model — BNK.RLVR.CAP.BSP.001.TIE (Tier Management)

> **Layer**: Process Modelling (DDD tactical) — sits between Big-Picture Event Storming
> (banking-knowledge: BCM, FUNC ADR) and Software Design (this repo's `sources/`).
> **Source of truth for**: commands accepted, aggregate boundaries, reactive policies,
> read-model surface, bus topology, wire schemas of this capability.
> **NOT a plan**: this folder is durable across re-plans and re-implementations of the
> same FUNC ADR. The future `plan/BNK.RLVR.CAP.BSP.001.TIE/` folder consumes it.

## Upstream knowledge (consumed, not re-stated)

Fetched via `bcm-pack pack BNK.RLVR.CAP.BSP.001.TIE --deep`. Anything in those slices is
canonical and must NOT be duplicated here:

- `capabilities-reliever-L2.yaml` — capability definition, parent (BNK.RLVR.CAP.BSP.001), zone (BSP), owner
- `func-adr/ADR-BCM-FUNC-0005` — L2 breakdown of BNK.RLVR.CAP.BSP.001 (also governs SCO, SIG, ARB)
- `business-event-reliever.yaml` — `BNK.RLVR.EVT.BSP.001.TIER_UPGRADED`, `BNK.RLVR.EVT.BSP.001.TIER_DOWNGRADED`, `BNK.RLVR.EVT.BSP.001.TIER_OVERRIDE_APPLIED`
- `resource-event-reliever.yaml` — `BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED`, `BNK.RLVR.RVT.BSP.001.TIER_DOWNGRADE_RECORDED`, `BNK.RLVR.RVT.BSP.001.OVERRIDE_ACTIVATED`
- `business-object-reliever.yaml` — `BNK.RLVR.OBJ.BSP.001.TIER_CHANGE`, `BNK.RLVR.OBJ.BSP.001.ALGORITHMIC_OVERRIDE`
- `resource-reliever.yaml` — `BNK.RLVR.RES.BSP.001.TIER_UPGRADE`, `BNK.RLVR.RES.BSP.001.TIER_DOWNGRADE`, `BNK.RLVR.RES.BSP.001.ACTIVE_OVERRIDE`
- Sibling capability event surfaces (consumed by TIE):
  - `BNK.RLVR.CAP.BSP.001.SCO` — emits `BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED`
  - `BNK.RLVR.CAP.BSP.001.ARB` — emits `BNK.RLVR.RVT.BSP.001.ARBITRATION_OVERRIDE_VALIDATED`, `BNK.RLVR.RVT.BSP.001.OVERRIDE_CLOSED`
  - `BNK.RLVR.CAP.REF.001.TIE` — owns canonical tier definitions (read-through; future `BNK.RLVR.EVT.REF.001.TIER_DEFINITION_UPDATED` cache-sync subscription)
- `tech-vision/adr/ADR-TECH-STRAT-001` — bus topology rules (NORMATIVE)

## What this folder declares (Process Modelling output)

| File | Captures |
|---|---|
| `aggregates.yaml` | `AGG.BSP.001.TIE.TIER_OF_CASE` — consistency boundary; invariants on tier uniqueness, override exclusion, idempotency, realignment-on-closure |
| `commands.yaml` | `CMD.*` — APPLY_TIER_TRANSITION (algo), APPLY_PRESCRIBER_OVERRIDE (prescriber), CONFIRM_PRESCRIBER_OVERRIDE (ARB), CLOSE_PRESCRIBER_OVERRIDE (ARB) |
| `policies.yaml` | `POL.*` — reactive rules wiring SCO threshold and ARB validation/closure events to commands; placeholders for enrolment seeding and REF cache sync |
| `read-models.yaml` | `PRJ.*` + `QRY.*` — current tier view + tier history projection, two GET endpoints |
| `api.yaml` | Derived REST surface — POST tier transitions, POST overrides, GET current tier, GET tier history |
| `bus.yaml` | Exchange `bsp.001.tie-events`, three routing keys, three upstream subscriptions, four known consumers |
| `schemas/` | JSON Schemas for all four commands and three emitted resource events (Draft 2020-12) |

## Scenario walkthroughs

Three flows — **algorithmic transition**, **prescriber override lifecycle**, and
**override realignment** — drive every behaviour of this capability.

### Flow A — Algorithmic tier transition on score threshold

```
[BNK.RLVR.CAP.BSP.001.SCO]
  emits BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED
  routing-key BNK.RLVR.EVT.BSP.001.SCORE_THRESHOLD_REACHED.BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED
            │
            ▼
  POL.BSP.001.TIE.ON_SCORE_THRESHOLD_REACHED
            │
            ▼ issues
  CMD.BSP.001.TIE.APPLY_TIER_TRANSITION { case_id, trigger, transition }
            │
            ▼ handled by
  AGG.BSP.001.TIE.TIER_OF_CASE
            │
            ├── INV.TIE.002 — rejected if active override (ack-and-drop)
            │
            ▼ on success, emits exactly one of
  BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED   (paired BNK.RLVR.EVT.TIER_UPGRADED)
   OR
  BNK.RLVR.RVT.BSP.001.TIER_DOWNGRADE_RECORDED (paired BNK.RLVR.EVT.TIER_DOWNGRADED)
            │
            ▼ consumed by
  BNK.RLVR.CAP.BSP.004.ENV (envelope reallocation)
  BNK.RLVR.CAP.B2B.001.CRD (card rule reconfiguration)
  BNK.RLVR.CAP.CHN.001.DSH (dashboard celebration / soft notice)
```

### Flow B — Prescriber override lifecycle

```
[Prescriber action via BNK.RLVR.CAP.CHN.002.VUE]
  POST /cases/{case_id}/overrides
            │
            ▼ issues directly (no upstream event)
  CMD.BSP.001.TIE.APPLY_PRESCRIBER_OVERRIDE { override_id, applied_tier_code, rationale }
            │
            ▼ handled by
  AGG.BSP.001.TIE.TIER_OF_CASE  (state.active_override.validation_state = PENDING_ARBITRATION)
            │
            ▼ emits
  BNK.RLVR.RVT.BSP.001.OVERRIDE_ACTIVATED   (paired BNK.RLVR.EVT.TIER_OVERRIDE_APPLIED)
            │
            ▼ consumed by
  BNK.RLVR.CAP.BSP.001.ARB  (begins validation cycle)
            │
            ▼ ARB eventually emits ONE of:
  BNK.RLVR.RVT.BSP.001.ARBITRATION_OVERRIDE_VALIDATED   (paired BNK.RLVR.EVT.ARBITRATION_OVERRIDE_VALIDATED)
            │
            ▼
  POL.BSP.001.TIE.ON_ARBITRATION_OVERRIDE_VALIDATED
            │
            ▼ issues
  CMD.BSP.001.TIE.CONFIRM_PRESCRIBER_OVERRIDE
            │
            ▼ silent state transition: PENDING_ARBITRATION → CONFIRMED_BY_ARBITRATION
            ▼ no bus event emitted (ARB already published the validation)

  --- OR, later, ARB decides to close the override and emits ---
  BNK.RLVR.RVT.BSP.001.OVERRIDE_CLOSED   (paired BNK.RLVR.EVT.ARBITRATION_ALGORITHM_REAFFIRMED)
            │
            ▼  see Flow C
```

### Flow C — Override realignment on closure

```
[BNK.RLVR.CAP.BSP.001.ARB]
  emits BNK.RLVR.RVT.BSP.001.OVERRIDE_CLOSED
  routing-key BNK.RLVR.EVT.BSP.001.ARBITRATION_ALGORITHM_REAFFIRMED.BNK.RLVR.RVT.BSP.001.OVERRIDE_CLOSED
  payload carries algorithmic_tier_at_closure (computed from latest score state)
            │
            ▼
  POL.BSP.001.TIE.ON_ARBITRATION_ALGORITHM_REAFFIRMED
            │
            ▼ issues
  CMD.BSP.001.TIE.CLOSE_PRESCRIBER_OVERRIDE
            │
            ▼ handled by
  AGG.BSP.001.TIE.TIER_OF_CASE
            │
            ├── clears state.active_override
            │
            ▼ INV.TIE.005: compare algorithmic_tier_at_closure vs override.applied_tier_code
            │
            ├── if EQUAL: silent closure, no bus event
            │
            ├── if algorithmic > override: emits BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED
            │                              with transition.cause = OVERRIDE_REALIGNMENT
            │
            └── if algorithmic < override: emits BNK.RLVR.RVT.BSP.001.TIER_DOWNGRADE_RECORDED
                                          with transition.cause = OVERRIDE_REALIGNMENT
            │
            ▼ consumers see the corrected tier with full causation lineage
              via transition.trigger_event_id pointing at the OVERRIDE_CLOSED event
```

## Open process-level questions (must be resolved before `/code`)

- **Missing BCM subscription chain for TIE consumption.** The producer-side
  bus topologies of BNK.RLVR.CAP.BSP.001.SCO and BNK.RLVR.CAP.BSP.001.ARB list `BNK.RLVR.CAP.BSP.001.TIE`
  as a consumer of `BNK.RLVR.EVT.SCORE_THRESHOLD_REACHED.#` and the two ARB events.
  However, the corresponding `BNK.RLVR.SUB.BUSINESS.BSP.001.TIE.{001..003}` and
  `BNK.RLVR.SUB.RESOURCE.BSP.001.TIE.{001..003}` entries do **not** exist in the BCM
  YAML. They must be authored in `banking-knowledge` before `/code` runs;
  the `bus.yaml` file declares the IDs we expect.

- **Initial tier seeding — lazy vs proactive.** This sketch picks **lazy
  materialisation**: the aggregate is created on the first algorithmic
  transition or override, with `current_tier_code` resolved by read-through
  to `BNK.RLVR.CAP.REF.001.TIE`. The alternative is `POL.ON_BENEFICIARY_ENROLLED`
  (kept here as a placeholder) issuing a `CMD.SEED_INITIAL_TIER` that
  silently materialises the aggregate (no new BCM event is invented). The
  read model `PRJ.CURRENT_TIER_VIEW` already implements a fallback that
  returns the entry tier from REF when no transition has been recorded —
  consumers see no `404` regardless of which path is chosen. Revisit if
  dashboards need TIE to publish the entry tier as an explicit event.

- **Algorithmic-tier-at-closure source.** `CMD.CLOSE_PRESCRIBER_OVERRIDE`
  needs the algorithmic tier the case "would" be in to decide whether to
  emit a realignment transition (INV.TIE.005). This sketch assumes ARB
  carries it in the `OVERRIDE_CLOSED` payload (`algorithmic_tier_code` +
  `score_event_id`). If ARB cannot supply it, TIE must query
  `BNK.RLVR.CAP.BSP.001.SCO` at command time — a synchronous cross-capability call
  that breaks the event-driven model for this branch. Confirm with the ARB
  process model when authored.

- **TIE-side event on arbitration confirmation?** Sketch says **no** — when
  TIE transitions an override from `PENDING_ARBITRATION` to
  `CONFIRMED_BY_ARBITRATION` via `CMD.CONFIRM_PRESCRIBER_OVERRIDE`, no bus
  event is emitted (ARB already published the validation). Revisit if
  downstream consumers (dashboard, prescriber view, audit pipeline) need a
  TIE-side confirmation for lineage.

- **Override target above or below current tier — both legal?** This sketch
  permits either direction. ARB validates whether the override is
  appropriate; TIE only ensures the target tier exists in REF. Confirm with
  FUNC-0005 / the ARB process model that prescriber overrides are not
  restricted to one direction.

- **Mutual exclusion behaviour on score threshold during override.** Sketch
  picks `ack-and-drop` for `OVERRIDE_IN_FORCE` errors. The next score
  threshold after override closure re-drives the algorithmic decision. The
  alternative would be queuing the threshold event for replay after closure
  — but that introduces an unbounded queue and complicates the closure
  realignment logic. The current choice is simpler and aligns with the
  realignment invariant (INV.TIE.005).

## Governance

| ADR | Role |
|---|---|
| `ADR-BCM-FUNC-0005` | L2 breakdown of BNK.RLVR.CAP.BSP.001 — defines emitted/consumed events for SCO, TIE, SIG, ARB |
| `ADR-BCM-URBA-0007/8/9` | Event meta-model + capability event ownership |
| `ADR-BCM-URBA-0010/11` | L2 as urbanisation pivot, local L3 decomposition |
| `ADR-BCM-URBA-0012` | Canonical concepts (CPT.BCM.000.TIER governs tier semantics) |
| `ADR-TECH-STRAT-001` | Bus rules (exchange-per-L2, routing-key form `<EVT>.<RVT>`, payload form domain-event-DDD) |
