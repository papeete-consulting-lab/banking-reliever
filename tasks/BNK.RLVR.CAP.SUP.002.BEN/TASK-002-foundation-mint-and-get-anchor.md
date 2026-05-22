---
task_id: TASK-002
capability_id: BNK.RLVR.CAP.SUP.002.BEN
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Beneficiary Identity Anchor
epic: Epic 2 — Foundation (anchor minting and synchronous lookup)
status: done
priority: high
depends_on: []
task_type: full-microservice
loop_count: 0
max_loops: 10
pr_url: https://github.com/Banking-PapeeteConsulting/banking-reliever/pull/15
---

> **Started on:** 2026-05-16
> **Submitted for review on:** 2026-05-16

# TASK-002 — Foundation: mint anchor (UUIDv7) and serve synchronous lookup

## Context
This task delivers the smallest version of `BNK.RLVR.CAP.SUP.002.BEN` that has business
value: an anchor can be minted (UUIDv7 server-generated) and resolved
synchronously by `internal_id`. From the moment this lands, every other
capability that needs canonical beneficiary identity has a working API to
call AND a working bus event family to subscribe to — Wave C and beyond
(Epics 3–6) extend this nucleus rather than replacing it. TASK-001 (stub)
runs in parallel, fully orthogonal: it covers contract on the wire side
without preempting real persistence.

The MINT path is the canonical entry point for `internal_id` minting per
`ADR-TECH-STRAT-007` (RFC-9562 UUIDv7, k-sortable, no-recycle-forever). The
GET path serves `QRY.SUP.002.BEN.GET_ANCHOR` from the
`PRJ.SUP.002.BEN.ANCHOR_DIRECTORY` projection, eventually-consistent with
the aggregate.

## Capability Reference
- Capability: Beneficiary Identity Anchor (BNK.RLVR.CAP.SUP.002.BEN)
- Zone: SUPPORT
- Governing FUNC ADR: ADR-BCM-FUNC-0016
- Strategic-tech anchors: ADR-TECH-STRAT-001 (transactional outbox, Rule 3),
  ADR-TECH-STRAT-003 (REST/JWT), ADR-TECH-STRAT-004 (PII / dual access),
  ADR-TECH-STRAT-007 (UUIDv7 minting, idempotency-as-identifier),
  ADR-TECH-STRAT-008 (multi-faceted producer)
- Tactical stack: ADR-TECH-TACT-002 (Python + FastAPI + PostgreSQL +
  pgcrypto + Vault transit + crypto-shredding) — pgcrypto/Vault are
  provisioned but not exercised until TASK-005

## What to Build
The real microservice scaffold under `sources/BNK.RLVR.CAP.SUP.002.BEN/backend/`
implementing the MINT command path and the synchronous GET query path of
the `AGG.SUP.002.BEN.IDENTITY_ANCHOR` aggregate.

1. **Aggregate** — `AGG.SUP.002.BEN.IDENTITY_ANCHOR` with the state fields
   declared in `process/BNK.RLVR.CAP.SUP.002.BEN/aggregates.yaml` (identity, PII
   snapshot, lifecycle, idempotency, revision counter). Enforces
   `INV.BEN.001`, `INV.BEN.002`, `INV.BEN.007`, `INV.BEN.008` at MINT time.
2. **Command handler** — `CMD.SUP.002.BEN.MINT_ANCHOR` accepted by `POST
   /anchors` per `process/BNK.RLVR.CAP.SUP.002.BEN/api.yaml.mintAnchor`. Validates
   the request body against
   `process/BNK.RLVR.CAP.SUP.002.BEN/schemas/CMD.SUP.002.BEN.MINT_ANCHOR.schema.json`.
   Mints a RFC-9562 UUIDv7 `internal_id` server-side (callers cannot
   supply one). Persists the anchor row to PostgreSQL inside a
   transaction that also writes the outbox row.
3. **Idempotency** — deduplicates on `client_request_id` (UUIDv7, 30-day
   window, `INV.BEN.008`). On hit: returns `200 OK` with the original
   anchor (NOT `201`, NOT `409`); error code surfaced is
   `REQUEST_ALREADY_PROCESSED` per `commands.yaml`.
4. **Transactional outbox** — emits `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED`
   with `transition_kind: MINTED`, `revision: 1`, full post-transition
   snapshot, via the outbox pattern (`ADR-TECH-STRAT-001` Rule 3
   at-least-once). Routing key
   `BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED`
   on exchange `sup.002.ben-events`. Envelope carries UUIDv7
   `message_id` / `correlation_id` / `causation_id`.
5. **Projection** — `PRJ.SUP.002.BEN.ANCHOR_DIRECTORY` ingests the RVT and
   updates the directory row keyed on `internal_id` (last-write-wins on
   `revision`, out-of-order detection).
6. **Query handler** — `QRY.SUP.002.BEN.GET_ANCHOR` served by `GET
   /anchors/{internal_id}` per `api.yaml.getAnchor`. Reads from
   `PRJ.ANCHOR_DIRECTORY`. Returns the `BeneficiaryAnchor` shape with
   ETag and `Cache-Control: max-age=60`; `304` on If-None-Match match;
   `404 ANCHOR_NOT_FOUND` on miss.

## Business Events to Produce
- `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with `transition_kind: MINTED` —
  emitted when `CMD.MINT_ANCHOR` is successfully applied (anchor newly
  persisted, NOT on idempotent re-call).

## Business Objects Involved
- `BNK.RLVR.OBJ.SUP.002.BENEFICIARY_RECORD` — minted by this task; foreign-key
  anchor for the rest of the IS
- `CPT.BCM.000.BENEFICIARY` — canonical concept carried by the new anchor

## Event Subscriptions Required
None. The capability has zero declared subscriptions in v1 (see
`policies.yaml`).

## Definition of Done
- [ ] Microservice scaffold under `sources/BNK.RLVR.CAP.SUP.002.BEN/backend/` per
      `ADR-TECH-TACT-002` (Python 3.12+, FastAPI, `psycopg`/`asyncpg`,
      `aio-pika`) — Domain / Application / Infrastructure / Presentation /
      Contracts packages
- [ ] `docker compose up` from the backend folder starts the service plus
      PostgreSQL plus RabbitMQ in dev
- [ ] PostgreSQL schema declares the `anchor_directory` table (primary
      key `internal_id`, columns matching `read-models.yaml.fields`) plus
      an `outbox` table (`ADR-TECH-STRAT-001` Rule 3)
- [ ] `POST /anchors` accepts the request, validates it against
      `schemas/CMD.SUP.002.BEN.MINT_ANCHOR.schema.json`, generates a
      RFC-9562 UUIDv7 (k-sortable, wall-clock-prefixed), persists the row,
      and returns `201 Created` with the new `BeneficiaryAnchor`
- [ ] Server-supplied `internal_id` in the request is **rejected** (the
      aggregate is the sole mint authority — `INV.BEN.001`)
- [ ] Re-posting the same `client_request_id` within the 30-day window
      returns `200 OK` with the original anchor and error code
      `REQUEST_ALREADY_PROCESSED` — no new row, no second outbox entry
- [ ] Missing `last_name` / `first_name` / `date_of_birth` returns `400
      IDENTITY_FIELDS_MISSING`
- [ ] On successful mint, one row appears in the outbox; the outbox
      relay publishes one `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` on
      `sup.002.ben-events` with routing key
      `BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED`
      and `transition_kind: MINTED`, `revision: 1`
- [ ] Emitted payload validates against
      `schemas/BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json`;
      envelope carries UUIDv7 `message_id`, `correlation_id`,
      `causation_id`
- [ ] `GET /anchors/{internal_id}` returns the anchor with ETag and
      `Cache-Control: max-age=60`; `If-None-Match` matching the current
      ETag returns `304`; unknown ID returns `404 ANCHOR_NOT_FOUND`
- [ ] Eventual-consistency contract is honoured — a `GET` issued
      milliseconds after `POST` may legitimately return `404` until the
      projection catches up; integration test covers both the immediate
      window and the post-catch-up window
- [ ] Authentication: the `actor` typed object is captured server-side
      and written to the RVT envelope per `bus.yaml.publication.envelope.actor`
      (v0.2.0 shape: `{kind: human|service|system, subject, on_behalf_of?}`).
      For human callers, `kind = human` and `subject` = JWT `sub` claim
      per `ADR-TECH-STRAT-003`; for service-to-service, `kind = service`
      and `subject` = capability id of the caller; for outbox replay or
      scheduled jobs, `kind = system` and `subject` = a stable
      `system:*` token. `on_behalf_of` is set when the human is acting
      for another principal (DPO admin tooling, support staff). The
      `actor` is recorded in the outbox row and propagated into the
      RVT envelope; downstream consumption into `PRJ.ANCHOR_HISTORY` is
      TASK-006's concern.
- [ ] No write to `process/BNK.RLVR.CAP.SUP.002.BEN/` (read-only)
- [ ] If a `sources/BNK.RLVR.CAP.SUP.002.BEN/stub/` from TASK-001 is present,
      the README of the stub is updated to note that the MINT + GET
      surface is now served by the real service; the stub remains
      runnable for the still-unimplemented transitions (UPDATED,
      ARCHIVED, RESTORED, PSEUDONYMISED)
- [ ] Self-validation `pytest` suite covers: UUIDv7 format compliance,
      idempotency hit/miss, schema validation of emitted RVT, 400/404
      paths, ETag/304 path

## Acceptance Criteria (Business)
A downstream capability (Enrolment, in practice) can `POST /anchors` with
a beneficiary's natural identity plus a UUIDv7 `client_request_id` and
receive back the new `internal_id` synchronously. Retrying the same
`client_request_id` returns the same `internal_id` — no duplicates. The
SCO / ENR / ENV / DSH / VIE / RET capabilities can bind to
`sup.002.ben-events` and observe the MINTED event within the
at-least-once delivery window. A consumer that calls
`GET /anchors/{internal_id}` resolves the anchor reliably within the
projection-catch-up window.

## Dependencies
- TASK-001: not strictly required (stub is orthogonal), but its existence
  validates the bus topology and Python toolchain shape before this task
  starts. Real-implementation tasks (TASK-002+) do **not** declare
  `depends_on: [TASK-001]` — they run in parallel with the stub.
- PostgreSQL available in the dev environment
- RabbitMQ available in the dev environment

## Open Questions
- [x] OQ.BEN.002 (`external_id` removal) — RESOLVED upstream by PR #12
      (`process(BNK.RLVR.CAP.SUP.002.BEN): refine — drop external_id mentions`)
      and PR #13 (`chore(roadmap): scrub external_id mentions from
      non-EXB roadmaps`). The decision: `external_id` is not part of
      the SUPPORT-zone model — consumers that previously used it as a
      candidacy reference now key their own correlation field on the
      way in and observe the MINTED RVT to learn the `internal_id`.
      No new BCM business-event is required. The audit-trail entry is
      preserved per the `/sort-task` convention.
