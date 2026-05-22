---
task_id: TASK-003
capability_id: BNK.RLVR.CAP.SUP.002.BEN
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Beneficiary Identity Anchor
epic: Epic 3 — Identity update with sticky-PII semantics
status: done
priority: high
depends_on: [TASK-002]
task_type: full-microservice
loop_count: 0
max_loops: 10
pr_url: https://github.com/Banking-PapeeteConsulting/banking-reliever/pull/16
---

> **Started on:** 2026-05-16
> **Submitted for review on:** 2026-05-16

# TASK-003 — Update anchor PII with sticky-field semantics

## Context
Once anchors can be minted, the next operational verb is updating their PII
— typically a contact channel change, occasionally a legal name change.
This task establishes the **sticky-PII invariant** (`INV.BEN.003`) that
distinguishes this capability from a naive mass-update endpoint: absent
fields in the payload are no-ops, only explicitly present fields are
mutated, and a contact channel can only be cleared via an explicit
nullability marker. PII destruction must NEVER flow through this command
— it has its own auditable path via `PSEUDONYMISE_ANCHOR` (TASK-005).

Epic 3 can run in parallel with Epic 4 (TASK-004 archive/restore) — both
extend the aggregate's command surface independently.

## Capability Reference
- Capability: Beneficiary Identity Anchor (BNK.RLVR.CAP.SUP.002.BEN)
- Zone: SUPPORT
- Governing FUNC ADR: ADR-BCM-FUNC-0016
- Strategic-tech anchors: ADR-TECH-STRAT-001 (outbox), ADR-TECH-STRAT-003
  (REST), ADR-TECH-STRAT-004 (PII), ADR-TECH-STRAT-007 (idempotency)
- Tactical stack: ADR-TECH-TACT-002

## What to Build
Extend the microservice from TASK-002 to handle `CMD.SUP.002.BEN.UPDATE_ANCHOR`.

1. **Command handler** — `PATCH /anchors/{internal_id}` per
   `api.yaml.updateAnchor`. Validates the body against
   `schemas/CMD.SUP.002.BEN.UPDATE_ANCHOR.schema.json`. Applies only
   fields explicitly present (sticky-PII, `INV.BEN.003`).
2. **Field-presence semantics** — distinguish "absent" (no-op) from
   "explicit null" (clear the channel). Use a dedicated nullability
   marker in the schema (e.g. `JSON null` vs missing key) so the
   intent is unambiguous on the wire.
3. **State-machine guard** — reject with `409` when the target anchor's
   `anchor_status` is `ARCHIVED` (`ANCHOR_ARCHIVED`) or `PSEUDONYMISED`
   (`ANCHOR_PSEUDONYMISED`). `404 ANCHOR_NOT_FOUND` on unknown
   `internal_id`. `400 NO_FIELDS_TO_UPDATE` on an empty effective payload.
4. **Idempotency** — deduplicates on `command_id` (UUIDv7, 30-day window,
   `INV.BEN.008`). On hit: `200 OK` with the prior post-transition
   snapshot and error code `COMMAND_ALREADY_PROCESSED`.
5. **Revision** — increments `revision` by 1 on successful application.
6. **Outbox** — emits one `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with
   `transition_kind: UPDATED`, full post-transition snapshot, revision
   bumped. Same routing key / exchange / envelope rules as TASK-002.
7. **Projection** — the `PRJ.ANCHOR_DIRECTORY` projection consumes the
   UPDATED event and overwrites the row (last-write-wins on
   `(internal_id, revision)`). Out-of-order events with `revision ≤`
   locally-observed are dropped.

## Business Events to Produce
- `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with `transition_kind: UPDATED`,
  `revision = N+1` — emitted when an UPDATE command is successfully
  applied (NOT on idempotent re-call).

## Business Objects Involved
- `BNK.RLVR.OBJ.SUP.002.BENEFICIARY_RECORD` — mutated in place; `internal_id`
  remains immutable (`INV.BEN.002`)

## Event Subscriptions Required
None.

## Definition of Done
- [ ] `PATCH /anchors/{internal_id}` accepts requests, validates against
      `schemas/CMD.SUP.002.BEN.UPDATE_ANCHOR.schema.json`
- [ ] An absent field is a no-op; an explicit `null` on a contact channel
      clears it — both cases covered by unit and integration tests
      (`INV.BEN.003`)
- [ ] `internal_id` is **never** mutated by an UPDATE — even if the
      payload tries to set it, the aggregate refuses (`INV.BEN.002`)
- [ ] `command_id` deduplication: a duplicate within the 30-day window
      returns `200 OK` with the prior post-transition snapshot and
      `COMMAND_ALREADY_PROCESSED`; no second outbox row
- [ ] `404 ANCHOR_NOT_FOUND` when no anchor matches the path parameter
- [ ] `409 ANCHOR_ARCHIVED` when `anchor_status = ARCHIVED`
- [ ] `409 ANCHOR_PSEUDONYMISED` when `anchor_status = PSEUDONYMISED`
- [ ] `400 NO_FIELDS_TO_UPDATE` when the effective payload is empty
- [ ] On success, exactly one outbox row emerges; the outbox relay
      publishes one RVT with `transition_kind: UPDATED`, `revision =
      N+1`, full snapshot
- [ ] Emitted payload validates against
      `schemas/BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json`
- [ ] `PRJ.ANCHOR_DIRECTORY` ingests the event and overwrites the row;
      `GET /anchors/{internal_id}` reflects the change with the bumped
      `revision` after the projection-catch-up window; the ETag changes
      immediately even if the cached body lingers up to `max-age=60`
- [ ] Out-of-order delivery test: ingesting an UPDATED event whose
      `revision` is lower than the projection's current revision is
      dropped (`update_strategy` in `read-models.yaml`)
- [ ] No write to `process/BNK.RLVR.CAP.SUP.002.BEN/`
- [ ] `pytest` suite covers: presence/absence semantics, explicit-null
      clearing, idempotency hit/miss, state-machine guards (404/409),
      revision monotonicity, out-of-order drop

## Acceptance Criteria (Business)
A downstream operator can correct a beneficiary's contact channels
through `PATCH /anchors/{internal_id}` with confidence that absent fields
will not silently erase existing PII — only fields explicitly set in the
payload are touched. Subscribers see the `UPDATED` event with the new
snapshot. Archived and pseudonymised anchors cannot be silently mutated
— the state machine refuses with 409. The audit trail (via the
not-yet-built history projection, TASK-006) will record one row per
applied UPDATE; idempotent re-calls do not pollute it.

## Dependencies
- TASK-002 — foundation (aggregate, projection, outbox, schemas in place)

## Open Questions
None — `INV.BEN.003` is fully specified by the process model. The
encoding of "absent vs explicit null" on the wire (e.g. JSON Patch,
special sentinel) is left to the implementer per `ADR-TECH-TACT-002` —
the model only constrains observable behaviour.
