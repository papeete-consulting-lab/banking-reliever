---
task_id: TASK-002
capability_id: BNK.RLVR.CAP.BSP.001.SCO
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Behavioural Score
epic: Epic 1 — Contract and Development Stub (extension)
status: done
priority: high
depends_on: []
task_type: contract-stub
loop_count: 0
max_loops: 10
pr_url: https://github.com/Banking-Reliever/banking/pull/10
---

> **Started on:** 2026-05-15
> **Submitted for review on:** 2026-05-15
> **Merged on:** 2026-05-15 (PR #10)

# TASK-002 — Extend the development stub to the two remaining RVTs

## Context
`TASK-001` (PR #2 + remediation PR #5, both merged) shipped the first
iteration of the contract stub for `BNK.RLVR.CAP.BSP.001.SCO`, covering only
`BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED`. The process model has since
landed two new resource events in `process/BNK.RLVR.CAP.BSP.001.SCO/bus.yaml`
(v0.2.0) — `BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED` (Flow A baseline) and
`BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED` (paired with `CURRENT_SCORE_RECOMPUTED`
on threshold crossing per `INV.SCO.003`). This task extends the stub to
publish all three resource events, on the same exchange / topology, so
downstream consumers (`BNK.RLVR.CAP.BSP.001.ARB`, `BNK.RLVR.CAP.BSP.001.TIE`,
`BNK.RLVR.CAP.CHN.001.DSH`, `CAP.CHN.002.VUE`) can develop against the complete
frozen contract before the real algorithm (Epic 2) lands.

Schema authority has moved: the canonical schemas for all three RVTs now
live under `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/` (PR #8). The legacy copy
under `sources/BNK.RLVR.CAP.BSP.001.SCO/stub/.../schemas/BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED.schema.json`
must be retired: the stub validates against the canonical `process/`
location only.

## Capability Reference
- Capability: Behavioural Score (BNK.RLVR.CAP.BSP.001.SCO)
- Zone: BUSINESS_SERVICE_PRODUCTION
- Governing FUNC ADR: ADR-BCM-FUNC-0005
- Strategic-tech anchors: ADR-TECH-STRAT-001 (bus / Rule 2-3-4), ADR-TECH-STRAT-007 (UUIDv7 envelope), ADR-TECH-STRAT-008 (multi-faceted producer)
- Tactical stack: ADR-TECH-TACT-003 (Python + FastAPI + PostgreSQL + RabbitMQ operational rail + Kafka analytical rail)

## What to Build
A runnable extension of `sources/BNK.RLVR.CAP.BSP.001.SCO/stub/` that publishes
synthetic but contract-conforming payloads for **all three** resource
events declared in `process/BNK.RLVR.CAP.BSP.001.SCO/bus.yaml`. Adapt the existing
stub bundle:

1. **Publish three RVT families** on the owned topic exchange
   `bsp.001.sco-events`, with the routing keys mandated by `bus.yaml`:
   - `BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED.BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED` —
     simulated entry-score baselines (Flow A)
   - `BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED.BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED` —
     simulated recomputation outcomes (Flow B) — already covered by
     TASK-001, must keep working under the new schema source
   - `BNK.RLVR.EVT.BSP.001.SCORE_THRESHOLD_REACHED.BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED` —
     simulated threshold-crossing events, **bundled in the same emission
     batch** as a `CURRENT_SCORE_RECOMPUTED` whose score crosses a
     synthetic threshold (per `INV.SCO.003` — atomicity).
2. **Validate every outgoing payload** against the canonical schema under
   `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/RVT.*.schema.json` before publishing.
3. **Decommission the legacy schema location** —
   `sources/BNK.RLVR.CAP.BSP.001.SCO/stub/{src,test}/.../schemas/BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED.schema.json`
   is removed; the stub reads schemas from the `process/` folder (e.g.
   via a copy step at build time, or a path resolved relative to the
   repo root — the implementer chooses, but the canonical source of
   truth is `process/.../schemas/`).
4. **Carry the UUIDv7 envelope trio** (`message_id`, `correlation_id`,
   `causation_id`) on every published event per the
   `bus.yaml.publication.envelope` block (ADR-TECH-STRAT-007 Rule 4).
   `correlation_id` is the `case_id` UUIDv7; `causation_id` is a
   synthetic UUIDv7 (no upstream causation yet — this is the stub).
5. **Configurable cadence** — default 1–10 events/min across the three
   families combined, env-var overridable. Threshold events fire at a
   configurable probability per recomputation (default 1 in 10).
6. **Activate / deactivate** the entire emitter via `STUB_ACTIVE=true|false`.

## Events to Stub
- `BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED` — synthetic one-shot baseline per
  rotating fixture `case_id`; payload validates against
  `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED.schema.json`
- `BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED` — existing emitter; same
  fixtures, now validating against the canonical
  `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED.schema.json`
  (no functional change beyond the schema-source relocation)
- `BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED` — bundled with a
  `CURRENT_SCORE_RECOMPUTED` emission whose new score crosses a
  synthetic threshold; both messages publish atomically (transactional
  outbox or in-process two-message commit acceptable for a stub —
  implementer choice, but document it)

## Query Operations to Stub
None in this iteration. The `api.yaml` query surface (`GET
/cases/{case_id}/score`, `GET /cases/{case_id}/score-history`) is
delivered by Epic 4 (TASK-005). The stub stays bus-only, matching
TASK-001's scope.

## Business Objects Involved
- `BNK.RLVR.OBJ.BSP.001.EVALUATION` — carried by all three RVTs (full snapshot of
  the post-transition aggregate)

## Required Event Subscriptions
None — the stub is a pure producer.

## Definition of Done
- [ ] Stub source under `sources/BNK.RLVR.CAP.BSP.001.SCO/stub/` extended (no
      new microservice; reuse the existing bundle from TASK-001)
- [ ] `docker compose up` from the stub folder starts the worker + a
      local RabbitMQ; no PostgreSQL needed for the stub
- [ ] On startup the stub re-declares the `bsp.001.sco-events` topic
      exchange (durable=true, owner=BNK.RLVR.CAP.BSP.001.SCO) — idempotent with
      TASK-001's startup
- [ ] For each of the three `RVT.*` declared in `bus.yaml`, the stub
      publishes at least one synthetic event with the correct routing
      key from the bus topology
- [ ] Every emitted payload validates against the corresponding
      `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/RVT.*.schema.json` before
      publishing (fail-fast on contract drift)
- [ ] Threshold detection is atomic with recomputation: when the
      synthetic recomputation crosses a threshold, **both**
      `CURRENT_SCORE_RECOMPUTED` and `SCORE_THRESHOLD_REACHED` are
      published — never one without the other (`INV.SCO.003`)
- [ ] Every emitted envelope carries UUIDv7 `message_id`,
      `correlation_id` (set to the synthetic `case_id`), and
      `causation_id` (synthetic UUIDv7) per
      `bus.yaml.publication.envelope`
- [ ] Cadence configurable via env var; default 1–10 events/min combined
- [ ] Threshold-crossing probability configurable; default 1/10 of
      `CURRENT_SCORE_RECOMPUTED` emissions trigger a paired threshold
- [ ] `STUB_ACTIVE=false` halts all publication
- [ ] Self-validation unit test asserts: every kind of outgoing payload
      validates against its canonical schema; the atomicity invariant
      holds (threshold ⇒ paired recomputation) — runnable in CI without
      bus connectivity
- [ ] Legacy schema location
      `sources/BNK.RLVR.CAP.BSP.001.SCO/stub/{src,test}/.../schemas/BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED.schema.json`
      is removed (or proven to be a copy-at-build artefact, not an
      authored source) — the canonical schema location is
      `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/`
- [ ] **Decommissioning** — the stub's README is updated to state that
      the stub is retired (or kept inert via `STUB_ACTIVE=false`) once
      Epic 2 (TASK-003) ships the real `CURRENT_SCORE_RECOMPUTED` +
      `SCORE_THRESHOLD_REACHED` and Epic 3 (TASK-004) ships the real
      `ENTRY_SCORE_COMPUTED`; each RVT family is retired independently
      as its real producer reaches feature parity
- [ ] No write to `process/BNK.RLVR.CAP.BSP.001.SCO/` (schemas are read-only
      from there)

## Acceptance Criteria (Business)
A developer working on any anticipated consumer (`BNK.RLVR.CAP.BSP.001.ARB`,
`BNK.RLVR.CAP.BSP.001.TIE`, `BNK.RLVR.CAP.CHN.001.DSH`, `CAP.CHN.002.VUE`) can, with only
the artifacts produced by this task, bind a queue to `bsp.001.sco-events`
on any of the three routing-key families and receive validating
event payloads. When a `SCORE_THRESHOLD_REACHED` arrives it is always
accompanied by the matching `CURRENT_SCORE_RECOMPUTED` (atomicity), so
arbitration and tier-transition logic can be built against the same
ordering guarantees the real implementation will honour. No
consumer-side change is required when the real algorithm lands later.

## Dependencies
None. Real-implementation tasks (TASK-003..006) run in parallel with
this stub extension, not behind it.

## Open Questions
None — the three schemas are authored on `main` (PR #8 merged), the bus
topology is fixed, and the existing stub bundle is the natural carrier
for the extension. The schema-source relocation from
`sources/.../stub/schemas/` to `process/.../schemas/` is a mechanical
move with no contract change.
