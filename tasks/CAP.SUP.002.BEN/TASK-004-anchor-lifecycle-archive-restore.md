---
task_id: TASK-004
capability_id: CAP.SUP.002.BEN
capability_name: Beneficiary Identity Anchor
epic: Epic 4 — Anchor lifecycle (archive / restore)
status: in_progress
priority: medium
depends_on: [TASK-002]
task_type: full-microservice
loop_count: 0
max_loops: 10
---

> **Started on:** 2026-05-16 (redo after PR #18 closed — Copilot conflict-resolution untrusted)

# TASK-004 — Anchor lifecycle: archive and restore

## Context
Provides the operational verbs for **programme exit** (archive) and
**audited reversal** (restore). Archived anchors remain queryable so
historical references keep resolving (no broken foreign keys at
downstream consumers) but reject further `UPDATE` until `RESTORE` is
issued. RESTORE is a rare audited operation — typically reverses an
archival applied in error. Neither verb mutates PII; for PII destruction
use TASK-005 (`PSEUDONYMISE`).

This task is **behaviourally independent of TASK-003** (update) — they
extend the aggregate in different directions and can run in parallel
after TASK-002 lands.

## Capability Reference
- Capability: Beneficiary Identity Anchor (CAP.SUP.002.BEN)
- Zone: SUPPORT
- Governing FUNC ADR: ADR-BCM-FUNC-0016
- Strategic-tech anchors: ADR-TECH-STRAT-001, ADR-TECH-STRAT-003,
  ADR-TECH-STRAT-007
- Tactical stack: ADR-TECH-TACT-002

## What to Build
Extend the microservice from TASK-002 to handle two lifecycle commands.

1. **`CMD.SUP.002.BEN.ARCHIVE_ANCHOR`** — `POST
   /anchors/{internal_id}/archive` per `api.yaml.archiveAnchor`.
   Validates against
   `schemas/CMD.SUP.002.BEN.ARCHIVE_ANCHOR.schema.json`. Requires a
   `reason` enum value: one of `PROGRAMME_EXIT_SUCCESS`,
   `PROGRAMME_EXIT_DROPOUT`, `PROGRAMME_EXIT_TRANSFER`,
   `ADMINISTRATIVE_ARCHIVAL`. Flips `anchor_status` `ACTIVE → ARCHIVED`
   (`INV.BEN.004`).
2. **`CMD.SUP.002.BEN.RESTORE_ANCHOR`** — `POST
   /anchors/{internal_id}/restore` per `api.yaml.restoreAnchor`.
   Validates against
   `schemas/CMD.SUP.002.BEN.RESTORE_ANCHOR.schema.json`. Flips
   `anchor_status` `ARCHIVED → ACTIVE` (`INV.BEN.005`). Does NOT mutate
   PII.
3. **State-machine guards** — both verbs reject with `409
   ANCHOR_PSEUDONYMISED` when status is PSEUDONYMISED (terminal,
   irreversible). ARCHIVE rejects with `409 ANCHOR_ALREADY_ARCHIVED`
   when already ARCHIVED. RESTORE rejects with `409 ANCHOR_NOT_ARCHIVED`
   when status is ACTIVE.
4. **Idempotency** — both verbs deduplicate on `command_id` (UUIDv7,
   30-day window). Duplicate `command_id` returns `200 OK` with the
   prior snapshot and `COMMAND_ALREADY_PROCESSED`.
5. **Outbox** — each successful transition emits one
   `RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with `transition_kind:
   ARCHIVED` or `RESTORED`, `revision = N+1`, full snapshot. Same
   routing key / exchange / envelope rules as TASK-002.
6. **GET continues to resolve archived anchors** — `GET
   /anchors/{internal_id}` still returns the record while archived
   (`anchor_status: ARCHIVED`); referential reads are not gated on
   status (`INV.BEN.004` — archived anchors stay queryable so historical
   references resolve).

## Business Events to Produce
- `RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with `transition_kind: ARCHIVED`
  — emitted on successful ARCHIVE
- `RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with `transition_kind: RESTORED`
  — emitted on successful RESTORE

## Business Objects Involved
- `OBJ.SUP.002.BENEFICIARY_RECORD` — `anchor_status` lifecycle field
  transitions; PII left unchanged

## Event Subscriptions Required
None.

## Definition of Done
- [ ] `POST /anchors/{internal_id}/archive` accepts requests, validates
      body against `schemas/CMD.SUP.002.BEN.ARCHIVE_ANCHOR.schema.json`
- [ ] `POST /anchors/{internal_id}/restore` accepts requests, validates
      body against `schemas/CMD.SUP.002.BEN.RESTORE_ANCHOR.schema.json`
- [ ] ARCHIVE flips `anchor_status` from ACTIVE to ARCHIVED on a fresh
      anchor; rejects with `409 ANCHOR_ALREADY_ARCHIVED` on a second
      ARCHIVE attempt; rejects with `409 ANCHOR_PSEUDONYMISED` if
      status is PSEUDONYMISED
- [ ] ARCHIVE rejects with `400` when `reason` is missing or not one of
      the four enum values
- [ ] RESTORE flips `anchor_status` from ARCHIVED back to ACTIVE;
      rejects with `409 ANCHOR_NOT_ARCHIVED` if status is ACTIVE;
      rejects with `409 ANCHOR_PSEUDONYMISED` if status is PSEUDONYMISED
- [ ] Both verbs return `404 ANCHOR_NOT_FOUND` for unknown
      `internal_id`
- [ ] Both verbs are idempotent on `command_id` (30-day window) —
      duplicates return `200 OK` with the prior snapshot and
      `COMMAND_ALREADY_PROCESSED`; no second outbox row
- [ ] Each successful transition produces exactly one outbox row; the
      relay publishes one RVT with the correct `transition_kind` and
      `revision = N+1`
- [ ] Emitted payloads validate against
      `schemas/RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json`
- [ ] PII fields in the snapshot are unchanged across ARCHIVE / RESTORE
      (`INV.BEN.002`); only `anchor_status` and `revision` change
- [ ] `GET /anchors/{internal_id}` continues to resolve archived
      anchors with status visible in the payload (`anchor_status:
      ARCHIVED`); ETag flips on every transition; cached body served up
      to `max-age=60`
- [ ] `PRJ.ANCHOR_DIRECTORY` ingests both transition kinds, last-write-
      wins on `(internal_id, revision)`, drops out-of-order events
- [ ] `UPDATE` (TASK-003) issued against an ARCHIVED anchor returns
      `409 ANCHOR_ARCHIVED` — cross-verb state-machine test
- [ ] No write to `process/CAP.SUP.002.BEN/`
- [ ] `pytest` suite covers: ACTIVE→ARCHIVED→ACTIVE round-trip,
      illegal transitions (409 paths), idempotency hit/miss, reason
      enum validation, snapshot continuity (PII unchanged)

## Acceptance Criteria (Business)
On programme exit, an operator can archive a beneficiary's anchor with a
documented `reason`; the anchor remains discoverable by downstream
consumers (no broken references) but is locked against further PII
updates. If the archival was a mistake, the operator can restore the
anchor to ACTIVE — and the audit trail (via TASK-006's history
projection, once built) shows both transitions cleanly. Pseudonymised
anchors are terminal — neither verb can resurrect them or break their
GDPR Art. 17 guarantees.

## Dependencies
- TASK-002 — foundation (aggregate, projection, outbox, schemas)

## Open Questions
None — both invariants (`INV.BEN.004`, `INV.BEN.005`) are fully specified
by the process model. The `reason` enum is fixed by the roadmap and the
schema; if business operators want additional values, route via FUNC ADR
+ `/process` re-run.
