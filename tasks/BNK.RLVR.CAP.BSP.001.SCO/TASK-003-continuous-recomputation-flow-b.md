---
task_id: TASK-003
capability_id: BNK.RLVR.CAP.BSP.001.SCO
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Behavioural Score
epic: Epic 2 — Continuous recomputation (Flow B)
status: todo
priority: high
depends_on: []
task_type: full-microservice
loop_count: 0
max_loops: 10
---

# TASK-003 — Continuous score recomputation (Flow B)

## Context
This task delivers the **differentiating algorithmic core** of
`BNK.RLVR.CAP.BSP.001.SCO` per the roadmap critical path: the real handler for
`CMD.RECOMPUTE_SCORE`, the reactive policy
`POL.BSP.001.SCO.ON_BEHAVIOURAL_TRIGGER` bound to the four upstream
queues, atomic emission of
`BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED` (always) and
`BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED` (when a threshold is crossed) per
`INV.SCO.003`, and the supporting transactional outbox. From this point
forward, every behavioural trigger flowing through the IS materialises a
real score transition.

The four homogeneous trigger kinds are `TRANSACTION_AUTHORIZED`,
`TRANSACTION_REFUSED`, `RELAPSE_SIGNAL`, `PROGRESSION_SIGNAL` per
`commands.yaml.trigger_kinds`. The policy maps each upstream resource
event to the same `CMD.RECOMPUTE_SCORE`, discriminating polarity and
weighting via the `trigger.kind` field. Identity resolution stays
producer-clean: the emitted payload carries `case_id` only, never
`internal_id` — consumers resolve to canonical identity via
`BNK.RLVR.CAP.SUP.002.BEN` (relocated from `CAP.REF.001.BEN` per
`ADR-BCM-FUNC-0016`).

## Capability Reference
- Capability: Behavioural Score (BNK.RLVR.CAP.BSP.001.SCO)
- Zone: BUSINESS_SERVICE_PRODUCTION
- Governing FUNC ADR: ADR-BCM-FUNC-0005
- Strategic-tech anchors: ADR-TECH-STRAT-001 (bus / Rule 3 outbox), ADR-TECH-STRAT-002 (modular monolith), ADR-TECH-STRAT-004 (identity resolution — `case_id` only on the producer side), ADR-TECH-STRAT-005 (OTel), ADR-TECH-STRAT-007 (UUIDv7 envelope), ADR-TECH-STRAT-008 (multi-faceted producer)
- Tactical stack: ADR-TECH-TACT-003 (Python + FastAPI + PostgreSQL + RabbitMQ operational rail + Kafka analytical rail via CDC of the outbox)

## What to Build
The real microservice scaffold under `sources/BNK.RLVR.CAP.BSP.001.SCO/backend/`
implementing Flow B.

1. **Aggregate** — `AGG.BSP.001.SCO.SCORE_OF_BENEFICIARY` (one instance
   per `case_id`) with the state declared in
   `process/BNK.RLVR.CAP.BSP.001.SCO/aggregates.yaml`: `case_id`, `entry_score`
   (nullable until initialised), `current_score`, `model_version`,
   `last_processed_trigger_event_id`, `tier_thresholds` (read-through).
   Enforces `INV.SCO.002` (entry-score precondition), `INV.SCO.003`
   (atomic threshold), `INV.SCO.004` (idempotency by
   `trigger.event_id`).
2. **Command handler** — `CMD.BSP.001.SCO.RECOMPUTE_SCORE` accepted from
   two paths:
   - **In-process from the policy** (canonical path) — see (3) below.
   - **HTTP back-channel** — `POST
     /capabilities/bsp/001/sco/cases/{case_id}/score-recomputations`
     per `process/BNK.RLVR.CAP.BSP.001.SCO/api.yaml.recomputeScore`. Validates
     the body against
     `schemas/CMD.BSP.001.SCO.RECOMPUTE_SCORE.schema.json`. Responses:
     `202` on accepted (canonical), `409 AGGREGATE_NOT_INITIALISED`,
     `200 TRIGGER_ALREADY_PROCESSED` (idempotent no-op).
3. **Policy** — `POL.BSP.001.SCO.ON_BEHAVIOURAL_TRIGGER` is bound to
   the four queues declared in `process/BNK.RLVR.CAP.BSP.001.SCO/bus.yaml`:
   `bsp.001.sco.q.transaction-authorized`,
   `bsp.001.sco.q.transaction-refused`,
   `bsp.001.sco.q.relapse-signal`,
   `bsp.001.sco.q.progression-signal`. Each queue is bound to its
   upstream exchange and binding pattern per the YAML. The policy maps
   the upstream RVT to a `CMD.RECOMPUTE_SCORE` per the
   `mapping_rule` in `process/BNK.RLVR.CAP.BSP.001.SCO/policies.yaml`
   (`case_id ← upstream.case_id`,
   `trigger.event_id ← upstream.event_id`, `trigger.kind` ← one of the
   four discriminators, `trigger.amount`/`trigger.category`/
   `trigger.impact_score` per the trigger kind).
4. **Tier-thresholds read-through** — the aggregate fetches the
   `tier_thresholds` configuration from `BNK.RLVR.CAP.BSP.001.TIE` at recomputation
   time (or caches it per the cache-invalidation policy chosen in
   answer to OQ-3 below). The thresholds are NOT replicated in this
   capability's persistent state — they are a configuration source.
5. **Atomic threshold detection** — when the new `current_score` crosses
   a threshold value (in either direction — upgrade or downgrade), the
   aggregate emits **both** `RVT.CURRENT_SCORE_RECOMPUTED` and
   `RVT.SCORE_THRESHOLD_REACHED` in the same transaction
   (`INV.SCO.003`). Never one without the other.
6. **Transactional outbox** (`ADR-TECH-STRAT-001` Rule 3) — persistent
   in PostgreSQL. The aggregate state mutation and the outbox row(s)
   commit atomically. A relay process publishes outbox rows to
   `bsp.001.sco-events` with the routing keys from `bus.yaml`. The same
   outbox is the source of truth for the analytical rail (Kafka CDC,
   per `ADR-TECH-STRAT-008`) — not part of this task, but the outbox
   schema must support it.
7. **Envelope** — every published event carries a fresh UUIDv7
   `message_id`, `correlation_id` set to the `case_id`, `causation_id`
   set to the upstream `trigger.event_id` (or the request's UUIDv7 for
   HTTP back-channel calls), and a `schema_version` semver per
   `bus.yaml.publication.envelope` (ADR-TECH-STRAT-007 Rule 4).
8. **Error handling** in the policy per `policies.yaml.error_handling`:
   `TRIGGER_ALREADY_PROCESSED` → ack-and-drop;
   `AGGREGATE_NOT_INITIALISED` → DLQ (operational anomaly — entry score
   missing); `BENEFICIARY_UNKNOWN` → DLQ (upstream emitted for unknown
   `case_id`).
9. **No identity leak** — the aggregate, the outbox, and every emitted
   payload reference `case_id` only, never `internal_id`. Code review
   and contract validation enforce this (ADR-TECH-STRAT-004 PII
   governance, bus.yaml.identity_resolution).
10. **OTel** — recomputation latency, trigger-kind distribution, DLQ
    depth per queue traced per `ADR-TECH-STRAT-005`. Detailed dashboards
    are Epic 5's job; this task only emits the spans / metrics so they
    can be aggregated later.

## Business Events to Produce
- `BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED` — emitted on **every**
  accepted `CMD.RECOMPUTE_SCORE`, carrying the post-transition
  `score_value`, `delta_score`, `model_version`, `evaluation_id`,
  `evenement_declencheur` (the trigger kind and reference)
- `BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED` — emitted **atomically alongside
  CURRENT_SCORE_RECOMPUTED** when the new score crosses a tier
  threshold (upgrade or downgrade), carrying the boundary metadata and
  the direction

## Business Objects Involved
- `BNK.RLVR.OBJ.BSP.001.EVALUATION` — the score-of-a-beneficiary aggregate root
  state, snapshotted into every emitted RVT

## Event Subscriptions Required
- `RVT.BSP.004.PAYMENT_GRANTED` (from `CAP.BSP.004.AUT`, binding
  `EVT.BSP.004.TRANSACTION_AUTHORIZED.RVT.BSP.004.PAYMENT_GRANTED`) —
  trigger_kind `TRANSACTION_AUTHORIZED`
- `RVT.BSP.004.PAYMENT_BLOCKED` (from `CAP.BSP.004.AUT`, binding
  `EVT.BSP.004.TRANSACTION_REFUSED.RVT.BSP.004.PAYMENT_BLOCKED`) —
  trigger_kind `TRANSACTION_REFUSED`
- `BNK.RLVR.RVT.BSP.001.RELAPSE_SIGNAL_QUALIFIED` (from `BNK.RLVR.CAP.BSP.001.SIG`) —
  trigger_kind `RELAPSE_SIGNAL`
- `BNK.RLVR.RVT.BSP.001.PROGRESSION_SIGNAL_QUALIFIED` (from `BNK.RLVR.CAP.BSP.001.SIG`) —
  trigger_kind `PROGRESSION_SIGNAL`

## Definition of Done
- [ ] Microservice scaffold under `sources/BNK.RLVR.CAP.BSP.001.SCO/backend/`
      per `ADR-TECH-TACT-003` (Python 3.12+, FastAPI, `psycopg`/
      `asyncpg`, `aio-pika`) — Domain / Application / Infrastructure /
      Presentation / Contracts packages
- [ ] `docker compose up` from the backend folder starts the service +
      PostgreSQL + RabbitMQ in dev
- [ ] PostgreSQL schema declares the aggregate table (one row per
      `case_id` with the state fields from `aggregates.yaml`), the
      outbox table (`ADR-TECH-STRAT-001` Rule 3), the
      `last_processed_trigger_event_id` index (idempotency)
- [ ] Four queues are declared and bound exactly per
      `process/BNK.RLVR.CAP.BSP.001.SCO/bus.yaml.subscriptions` (queue name,
      source exchange, binding pattern)
- [ ] `POL.ON_BEHAVIOURAL_TRIGGER` consumes from all four queues and
      issues `CMD.RECOMPUTE_SCORE` per the mapping rule in
      `policies.yaml`
- [ ] `INV.SCO.002` — recomputation rejects with
      `AGGREGATE_NOT_INITIALISED` when `entry_score` is null; the policy
      DLQs the message per `policies.yaml.error_handling`
- [ ] `INV.SCO.003` — when the new score crosses a threshold, both
      `CURRENT_SCORE_RECOMPUTED` and `SCORE_THRESHOLD_REACHED` are
      committed atomically (single transaction → outbox carries both
      → relay publishes both); integration test asserts a downstream
      consumer never receives one without the other
- [ ] `INV.SCO.004` — duplicate `trigger.event_id` (30d window) is
      silently dropped (idempotent no-op); ack-and-drop in the policy
- [ ] `POST /cases/{case_id}/score-recomputations` HTTP endpoint exists
      per `api.yaml.recomputeScore`; validates request against
      `schemas/CMD.BSP.001.SCO.RECOMPUTE_SCORE.schema.json`; returns
      `202` on accepted, `409 AGGREGATE_NOT_INITIALISED`,
      `200 TRIGGER_ALREADY_PROCESSED`
- [ ] Emitted payloads validate against
      `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED.schema.json`
      and `BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED.schema.json`
- [ ] Routing keys match `bus.yaml.publication.routing_keys` exactly
- [ ] Envelope carries UUIDv7 `message_id`, `correlation_id` (= `case_id`),
      `causation_id` (= upstream `trigger.event_id` or HTTP request
      UUIDv7) per `bus.yaml.publication.envelope`
- [ ] No emitted payload, no outbox row, no in-process log carries
      `internal_id` — the producer never resolves to canonical
      identity (`bus.yaml.identity_resolution`)
- [ ] OTel spans cover: command-handler, policy-handler-per-trigger-kind,
      outbox-relay; metrics expose recomputation rate per trigger kind
      and DLQ depth per queue
- [ ] Integration tests cover the four scenarios from the roadmap exit
      condition: positive trigger → recomputation only; negative trigger
      → recomputation only; trigger crossing threshold → recomputation
      + threshold (paired, atomic); duplicate trigger → ack-and-drop
- [ ] No write to `process/BNK.RLVR.CAP.BSP.001.SCO/`

## Acceptance Criteria (Business)
A behavioural trigger from any of the four upstream producers (a
transaction authorisation, a transaction refusal, a qualified relapse
signal, a qualified progression signal) flows through to the
beneficiary's score. The new score is committed atomically with its
event emission — no lost transitions, no duplicate transitions. When a
threshold is crossed, the tier-transition consumer (`BNK.RLVR.CAP.BSP.001.TIE`)
receives the paired threshold event in the same logical emission as the
recomputation event, never one without the other. Retries from the bus
(at-least-once delivery) are absorbed by the idempotency on
`trigger.event_id` — no double-counting.

## Dependencies
- TASK-002 is **not** a prerequisite (stub runs in parallel and is
  decommissioned per RVT family as this task lands its real
  implementation).
- See **Open Questions** below for upstream readiness
  (`CAP.BSP.004.AUT`, `BNK.RLVR.CAP.BSP.001.SIG`) and configuration source
  (`BNK.RLVR.CAP.BSP.001.TIE`).

## Open Questions
- [ ] **Upstream readiness — `CAP.BSP.004.AUT`** is not process-modelled
      and has no contract stub. Epic 2 cannot be end-to-end tested
      against `TRANSACTION_AUTHORIZED` / `TRANSACTION_REFUSED` until
      `CAP.BSP.004.AUT` ships its own TASK-001 contract stub
      (`RVT.BSP.004.PAYMENT_GRANTED` + `RVT.BSP.004.PAYMENT_BLOCKED`).
      Roadmap mitigation: build against the upstream's own development
      stub once merged. Resolution: either confirm AUT's contract stub
      is in the queue, or temporarily synthesise the two upstream RVTs
      from a local fixture for unit testing — but integration testing
      requires the real AUT stub.
- [ ] **Upstream readiness — `BNK.RLVR.CAP.BSP.001.SIG`** is not process-modelled
      either. Same mitigation as AUT. Until both are merged, two of the
      four trigger kinds (`RELAPSE_SIGNAL`, `PROGRESSION_SIGNAL`) cannot
      be exercised end-to-end. Confirm whether to ship Epic 2 in two
      waves (transactions first, signals second) or wait for both
      upstream stubs.
- [ ] **Tier-thresholds read-through cache invalidation** — the
      aggregate reads `tier_thresholds` from `BNK.RLVR.CAP.BSP.001.TIE`
      configuration. The roadmap (Open Question — "Tier-thresholds
      read-through caching") demands a cache-invalidation policy when
      `BNK.RLVR.CAP.BSP.001.TIE` updates its configuration. Specify the policy
      before implementing: TTL with re-fetch, event-driven invalidation
      subscribed to a `BNK.RLVR.CAP.BSP.001.TIE`-emitted RVT, or no cache
      (read-through on every recomputation). The choice affects
      throughput and the dependency graph.
