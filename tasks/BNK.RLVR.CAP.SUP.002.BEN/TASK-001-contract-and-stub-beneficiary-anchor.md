---
task_id: TASK-001
capability_id: BNK.RLVR.CAP.SUP.002.BEN
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Beneficiary Identity Anchor
epic: Epic 1 — Contract and Development Stub
status: done
priority: high
depends_on: []
task_type: contract-stub
loop_count: 0
max_loops: 10
pr_url: https://github.com/Banking-Reliever/banking/pull/9
---

> **Started on:** 2026-05-15

# TASK-001 — Contract and development stub for `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED`

## Context
`BNK.RLVR.CAP.SUP.002.BEN` is the canonical source of truth for beneficiary identity
across the Reliever IS — every other capability either subscribes to its
single emitted resource event or calls `GET /anchors/{internal_id}`
synchronously. Per `ADR-BCM-URBA-0009`, this capability owns the contract of
both its bus output and its REST surface. As long as the real microservice
is not built, this stub publishes the contracted RVTs on
`sup.002.ben-events` (one synthetic envelope per `transition_kind`) AND
serves the query API with canned cold data, so downstream consumers (the
SCO / ENR / ENV / DSH / VIE / AUD / RET migrations) can develop against the
wire format and the HTTP shape before the real microservice exists.

The bus topology (RabbitMQ topic exchange `sup.002.ben-events`, routing key
`BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED`,
payload form = domain-event DDD) is fixed by `ADR-TECH-STRAT-001`. The REST
surface (UUIDv7 path params, ETag/304) is fixed by `ADR-TECH-STRAT-003` +
`ADR-TECH-STRAT-007`. This is the **first non-.NET microservice** in the
programme — the stub is also the shake-down of the `implement-capability-python`
toolchain (`ADR-TECH-TACT-002`).

## Capability Reference
- Capability: Beneficiary Identity Anchor (BNK.RLVR.CAP.SUP.002.BEN)
- Zone: SUPPORT
- Governing FUNC ADR: ADR-BCM-FUNC-0016 (supersedes ADR-BCM-FUNC-0013)
- Strategic-tech anchors: ADR-TECH-STRAT-001 (bus), ADR-TECH-STRAT-003 (API),
  ADR-TECH-STRAT-004 (PII / dual-referential-access), ADR-TECH-STRAT-007
  (UUIDv7, immutable anchors), ADR-TECH-STRAT-008 (multi-faceted producer)
- Tactical stack: ADR-TECH-TACT-002 (Python + FastAPI + PostgreSQL + pgcrypto
  + Vault transit + crypto-shredding)

## What to Build
A runnable development stub under `sources/BNK.RLVR.CAP.SUP.002.BEN/stub/` that:

1. **Publishes resource events** for every transition kind declared in
   `process/BNK.RLVR.CAP.SUP.002.BEN/bus.yaml` — on the
   `sup.002.ben-events` topic exchange (durable, owned), routing key
   `BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED`,
   payload validates against
   `process/BNK.RLVR.CAP.SUP.002.BEN/schemas/BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json`.
   Synthetic emitter rotates across the five `transition_kind` values
   (`MINTED`, `UPDATED`, `ARCHIVED`, `RESTORED`, `PSEUDONYMISED`) at a
   configurable cadence (default 1–10 events/min). The `PSEUDONYMISED`
   variant exercises the conditional `if/then` of the schema (PII fields
   null, `right_exercise_id` set, `pseudonymized_at` set).
2. **Serves the query surface** for both operations declared in
   `process/BNK.RLVR.CAP.SUP.002.BEN/api.yaml` — `GET /anchors/{internal_id}` and
   `GET /anchors/{internal_id}/history` — returning canned cold data with
   ETag/304 honoured per the freshness policy in `read-models.yaml`.
   Pre-seeded with at least 3 stable fixtures (ACTIVE, ARCHIVED,
   PSEUDONYMISED) addressable by deterministic UUIDv7 IDs.
3. **Validates every outgoing payload** (bus and HTTP) against the
   corresponding JSON Schema before emission — fail-fast on contract drift.
4. **Carries the UUIDv7 envelope trio** on every published event
   (`message_id`, `correlation_id`, `causation_id`) per ADR-TECH-STRAT-007
   Rule 4.
5. **Is activatable / deactivatable** via `STUB_ACTIVE=true|false` (inactive
   in production).

## Events to Stub
- `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` (single emitted event family) —
  published on `sup.002.ben-events` with routing key
  `BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED`.
  Synthetic emitter cycles through all 5 `transition_kind` values:
  - `MINTED` — fresh UUIDv7, full PII fixture, `revision: 1`
  - `UPDATED` — same `internal_id` as a prior MINTED, mutated `contact_details`,
    `revision: N+1`
  - `ARCHIVED` — `anchor_status: ARCHIVED`, `reason` enum populated
  - `RESTORED` — `anchor_status: ACTIVE`, `revision` bumped
  - `PSEUDONYMISED` — PII fields null, `right_exercise_id` UUIDv7 set,
    `pseudonymized_at` set, `anchor_status: PSEUDONYMISED`

## Query Operations to Stub
- `GET /anchors/{internal_id}` — returns canned `BeneficiaryAnchor` from
  fixture set; `404 ANCHOR_NOT_FOUND` for unknown IDs; ETag/304 honoured
  with `max-age=60` per `QRY.SUP.002.BEN.GET_ANCHOR`.
- `GET /anchors/{internal_id}/history?since_revision=N` — returns canned
  `AnchorHistory` (PII-free) rows for the matching fixture; ETag/304
  honoured with `max-age=0`; `404 ANCHOR_NOT_FOUND` for unknown IDs.

## Business Objects Involved
- `BNK.RLVR.OBJ.SUP.002.BENEFICIARY_RECORD` — carried by every RVT, returned by
  `GET /anchors/{internal_id}` (PII fields nullable when PSEUDONYMISED)
- `CPT.BCM.000.BENEFICIARY` — canonical concept carried by the anchor (not
  authored here — declared upstream in the BCM)

## Event Subscriptions Required
None. `BNK.RLVR.CAP.SUP.002.BEN`'s BCM corpus declares zero consumed events in v1
(see `process/BNK.RLVR.CAP.SUP.002.BEN/policies.yaml` and OQ.BEN.001 in
`aggregates.yaml`). The stub is a producer + query server only.

## Definition of Done
- [ ] Stub source code under `sources/BNK.RLVR.CAP.SUP.002.BEN/stub/` (Python /
      FastAPI / `aio-pika`, per `ADR-TECH-TACT-002`)
- [ ] `docker compose up` from `sources/BNK.RLVR.CAP.SUP.002.BEN/stub/` starts the
      worker + FastAPI host + a local RabbitMQ for development
- [ ] On startup, the stub declares the `sup.002.ben-events` topic
      exchange (durable=true, owner=BNK.RLVR.CAP.SUP.002.BEN)
- [ ] For each of the 5 `transition_kind` values, the stub publishes at
      least one synthetic event with routing key
      `BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED`
- [ ] Every emitted payload validates against
      `process/BNK.RLVR.CAP.SUP.002.BEN/schemas/BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json`
      (including the conditional `if/then` for `PSEUDONYMISED`)
- [ ] Every emitted envelope carries UUIDv7 `message_id`, `correlation_id`,
      `causation_id` per ADR-TECH-STRAT-007 Rule 4
- [ ] Cadence is configurable via env var; default lies in 1–10 events/min
- [ ] `GET /anchors/{internal_id}` returns canned `BeneficiaryAnchor`
      payloads validating against the response shape declared in
      `process/BNK.RLVR.CAP.SUP.002.BEN/api.yaml`; ETag/304 honoured with
      `max-age=60`; `404` for unknown IDs
- [ ] `GET /anchors/{internal_id}/history` returns canned PII-free
      `AnchorHistory` rows; supports `?since_revision=N` filtering;
      ETag/304 honoured with `max-age=0`; `404` for unknown IDs
- [ ] At least 3 fixtures pre-seeded, retrievable by stable UUIDv7 IDs —
      one ACTIVE, one ARCHIVED, one PSEUDONYMISED (so consumers can write
      deterministic integration tests against the stub)
- [ ] `STUB_ACTIVE=false` halts both publication and HTTP serving (off in
      production)
- [ ] An automated self-validation test (`pytest`) validates each kind of
      outgoing payload against its schema — runnable in CI without bus / DB
- [ ] **Decommissioning note** in `sources/BNK.RLVR.CAP.SUP.002.BEN/stub/README.md`:
      the stub is retired (or permanently kept inert via `STUB_ACTIVE=false`)
      once TASK-002 ships the real `POST /anchors` + `GET /anchors/{id}` +
      MINTED RVT; further transition kinds get phased out as TASK-003
      through TASK-005 land
- [ ] No write to `process/BNK.RLVR.CAP.SUP.002.BEN/` (schemas are read-only from
      that folder — they are owned by `/process`)

## Acceptance Criteria (Business)
A developer working on any anticipated consumer of this capability — SCO,
ENR, ENV, DSH, VIE, B2B.FLW, AUD, RET — can, with only the artifacts
produced by this task: (a) bind a queue to `sup.002.ben-events` with
pattern `BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.#` and receive validating
event payloads covering all five transition kinds, including the
GDPR-Art.17 `PSEUDONYMISED` shape; AND (b) call `GET /anchors/{id}` and
`GET /anchors/{id}/history` and receive validating canned responses,
including the PSEUDONYMISED fixture where PII fields come back as null but
`internal_id` is still resolvable. No dependency on the real
implementation; no schema-driven or contract-driven consumer change is
required when the real implementation lands later (TASK-002+).

## Dependencies
None. This task is self-founding for the capability and is the shake-down
of the Python toolchain (first non-.NET microservice in the programme).

## Open Questions
None — the stub surface is fully determined by the merged process model.
If the implementer hits a tooling gap in `implement-capability-python`
(template, harness, integration), surface it as a TECH-TACT-002 delta
rather than improvising here.
