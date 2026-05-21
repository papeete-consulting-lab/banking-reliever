---
task_id: TASK-004
capability_id: BNK.RLVR.CAP.BSP.001.SCO
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Behavioural Score
epic: Epic 3 — Entry-score baseline (Flow A)
status: todo
priority: medium
depends_on: []
task_type: full-microservice
loop_count: 0
max_loops: 10
---

# TASK-004 — Entry-score baseline (Flow A)

## Context
Flow A is the one-shot enrolment baseline. When a beneficiary completes
enrolment upstream, this capability accepts `CMD.COMPUTE_ENTRY_SCORE`,
enforces `INV.SCO.001` (one-shot — exactly one entry score per
`case_id`), and emits `BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED`. The entry
score is the reference point against which every subsequent Flow B
recomputation (TASK-003) measures progression — `INV.SCO.002` rejects
recomputation when `entry_score` is null.

The canonical trigger is the upstream enrolment event from
`CAP.BSP.002.ENR`, picked up by `POL.ON_ENROLMENT_COMPLETED`. As of
2026-05-15 `CAP.BSP.002.ENR` is **not yet process-modelled** and the
governing FUNC ADR (`ADR-BCM-FUNC-0005`) lists **no business
subscription** for enrolment in `BNK.RLVR.CAP.BSP.001.SCO` — `policies.yaml`
marks `POL.ON_ENROLMENT_COMPLETED` with `status: placeholder` and an
explicit open question. This is the **hard blocker** flagged by the
roadmap. Until that chain lands upstream (BCM business subscription
registered + `CAP.BSP.002.ENR` process-modelled + its contract stub
shipped), Flow A can only be exercised via the HTTP back-channel
endpoint and against a stub for the enrolment trigger.

## Capability Reference
- Capability: Behavioural Score (BNK.RLVR.CAP.BSP.001.SCO)
- Zone: BUSINESS_SERVICE_PRODUCTION
- Governing FUNC ADR: ADR-BCM-FUNC-0005 (with FUNC-0006 as the
  anticipated upstream — `CAP.BSP.002.ENR`)
- Strategic-tech anchors: ADR-TECH-STRAT-001 (outbox), ADR-TECH-STRAT-003
  (REST), ADR-TECH-STRAT-004 (PII / identity resolution via
  `BNK.RLVR.CAP.SUP.002.BEN`), ADR-TECH-STRAT-007 (UUIDv7 envelope),
  ADR-TECH-STRAT-008 (multi-faceted producer)
- Tactical stack: ADR-TECH-TACT-003

## What to Build
Extend the microservice from TASK-003 to handle Flow A.

1. **Aggregate extension** — `AGG.BSP.001.SCO.SCORE_OF_BENEFICIARY`
   accepts `CMD.BSP.001.SCO.COMPUTE_ENTRY_SCORE`. The aggregate may not
   exist yet for the `case_id` (this is the initialisation command);
   on success, it initialises `entry_score` (which was `nullable_until_initialised`
   per `aggregates.yaml`) and persists the row.
2. **Invariants** — enforce `INV.SCO.001` (exactly one entry score per
   `case_id`; reject `ENTRY_SCORE_ALREADY_EXISTS` on retry). The
   precondition `PRE.002` (`BENEFICIARY_UNKNOWN`) resolves `case_id`
   against `BNK.RLVR.CAP.SUP.002.BEN` (canonical beneficiary identity, relocated
   from `CAP.REF.001.BEN`).
3. **HTTP endpoint** — `POST
   /capabilities/bsp/001/sco/cases/{case_id}/entry-score` per
   `api.yaml.computeEntryScore`. Validates the body against
   `schemas/CMD.BSP.001.SCO.COMPUTE_ENTRY_SCORE.schema.json`. Responses:
   `201` on first call, `409 ENTRY_SCORE_ALREADY_EXISTS`, `404
   BENEFICIARY_UNKNOWN`.
4. **Reactive policy — `POL.ON_ENROLMENT_COMPLETED`**. Per
   `policies.yaml`, listens to `EVT.BSP.002.ENROLMENT_COMPLETED` (or
   the resolved business + resource event chain once the BCM lands
   the subscription — see Open Questions). The policy maps the
   upstream payload to a `CMD.COMPUTE_ENTRY_SCORE`. On
   `ENTRY_SCORE_ALREADY_EXISTS` the policy acks-and-drops (duplicate
   enrolment notifications are tolerated per
   `policies.yaml.error_handling`). On `BENEFICIARY_UNKNOWN` the policy
   DLQs.
5. **Idempotency** on `case_id` (lifetime — entry score is a
   one-shot). Implemented as a uniqueness constraint on the aggregate
   row keyed by `case_id`.
6. **Outbox** emits `BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED` on success, on
   exchange `bsp.001.sco-events` with routing key
   `BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED.BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED`. Same
   atomic-commit + UUIDv7 envelope rules as TASK-003. Payload validates
   against
   `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED.schema.json`.
7. **Producer-clean identity** — the emitted RVT carries `case_id` only,
   never `internal_id`. The `BENEFICIARY_UNKNOWN` resolution against
   `BNK.RLVR.CAP.SUP.002.BEN` is a server-side pre-condition check; the resolved
   `internal_id` does NOT leak into the outbox or the bus.

## Business Events to Produce
- `BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED` — emitted on successful entry-score
  computation, carrying the baseline `score_value`, `model_version`,
  `evaluation_id`, `computation_timestamp`

## Business Objects Involved
- `BNK.RLVR.OBJ.BSP.001.EVALUATION` — initialised by this task; baseline state
  for all subsequent Flow B recomputations

## Event Subscriptions Required
- `EVT.BSP.002.ENROLMENT_COMPLETED` (anticipated, from
  `CAP.BSP.002.ENR`) — **not yet declared in the BCM** as a business
  subscription for this capability. Hard blocker — see Open Questions.

## Definition of Done
- [ ] `POST /cases/{case_id}/entry-score` accepts requests, validates
      against `schemas/CMD.BSP.001.SCO.COMPUTE_ENTRY_SCORE.schema.json`
- [ ] First call for a `case_id` returns `201 Created` with the
      computed entry-score; aggregate row is initialised
- [ ] Second call for the same `case_id` returns `409
      ENTRY_SCORE_ALREADY_EXISTS` (`INV.SCO.001`)
- [ ] Unknown `case_id` (no anchor in `BNK.RLVR.CAP.SUP.002.BEN`) returns `404
      BENEFICIARY_UNKNOWN`; the resolved `internal_id`, if any, does
      NOT leak into the response or the bus
- [ ] `POL.ON_ENROLMENT_COMPLETED` is wired up (no longer `status:
      placeholder` in `policies.yaml` — note: the YAML stays read-only;
      this DoD item is fulfilled when the upstream subscription is
      registered in the BCM and the policy is concretely bound — both
      driven by the Open Questions below)
- [ ] Policy on `ENTRY_SCORE_ALREADY_EXISTS` → ack-and-drop (duplicate
      enrolment notification — idempotent)
- [ ] Policy on `BENEFICIARY_UNKNOWN` → DLQ
- [ ] On success, one outbox row emerges; the relay publishes one RVT
      with routing key
      `BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED.BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED`
- [ ] Emitted payload validates against
      `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED.schema.json`
- [ ] Envelope carries UUIDv7 `message_id`, `correlation_id`
      (= `case_id`), `causation_id` (= upstream enrolment event ID or
      HTTP request UUIDv7) per `bus.yaml.publication.envelope`
- [ ] After this task, Flow B (TASK-003) on the same `case_id`
      succeeds: the recomputation handler no longer rejects with
      `AGGREGATE_NOT_INITIALISED` (`INV.SCO.002`); integration test
      covers the full Flow A → Flow B sequence on a fresh `case_id`
- [ ] No write to `process/BNK.RLVR.CAP.BSP.001.SCO/`
- [ ] Integration tests from the roadmap exit condition: nominal
      baseline (success), duplicate enrolment notification
      (ack-and-drop), unknown beneficiary (DLQ)

## Acceptance Criteria (Business)
When a beneficiary completes enrolment upstream, their behavioural-score
baseline is computed exactly once. Re-notification (a duplicate
enrolment-completed event) is absorbed silently. An attempt to enrol a
beneficiary not known to the canonical identity capability is rejected
and dead-lettered for operational follow-up. From this point on, every
transaction or behavioural signal flowing into Flow B can recompute the
score against a meaningful reference; the IS no longer carries
untethered behavioural scores.

## Dependencies
None modelled as TASK-NNN dependencies — the upstream readiness is
captured below as Open Questions because the referenced capabilities
are not yet process-modelled (no `TASK-NNN` exists to point at). When
they ship, this section may be updated to declare prefixed
dependencies on their TASK-001 contract stubs.

## Open Questions
- [ ] **HARD BLOCKER — enrolment trigger upstream missing.**
      `CAP.BSP.002.ENR` is not yet process-modelled; there is no
      contract stub, no committed BCM business subscription for
      enrolment in `BNK.RLVR.CAP.BSP.001.SCO`, and `ADR-BCM-FUNC-0005` lists
      none. `policies.yaml.POL.ON_ENROLMENT_COMPLETED` is marked
      `status: placeholder`. **Do not launch this task** until: (a)
      `CAP.BSP.002.ENR` is process-modelled in `process/CAP.BSP.002.ENR/`;
      (b) `EVT.BSP.002.ENROLMENT_COMPLETED` is declared with its paired
      resource event in the BCM; (c) a `SUB.BUSINESS` subscription for
      enrolment is registered for `BNK.RLVR.CAP.BSP.001.SCO` in the BCM; (d)
      `/process BNK.RLVR.CAP.BSP.001.SCO` is re-run to lift
      `POL.ON_ENROLMENT_COMPLETED` out of placeholder state. The
      pipeline tracker should keep this task in the "deferred" bucket
      per the roadmap "Recommended Sequencing" note.
- [ ] **`BNK.RLVR.CAP.SUP.002.BEN` foundation readiness** — the
      `BENEFICIARY_UNKNOWN` precondition resolves against
      `BNK.RLVR.CAP.SUP.002.BEN`. `BNK.RLVR.CAP.SUP.002.BEN/TASK-002` (`POST /anchors` +
      `GET /anchors/{id}`) must be done before this task can be
      end-to-end tested — otherwise the resolver has no real backing.
      The stub (`BNK.RLVR.CAP.SUP.002.BEN/TASK-001`) is sufficient for unit
      testing the resolution call shape, but not for the integration
      story.
