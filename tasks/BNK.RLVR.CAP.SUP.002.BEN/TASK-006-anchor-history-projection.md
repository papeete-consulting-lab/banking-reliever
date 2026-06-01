---
task_id: TASK-006
capability_id: BNK.RLVR.CAP.SUP.002.BEN
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Beneficiary Identity Anchor
epic: Epic 6 — Anchor history projection (audit trail)
status: in_review
priority: medium
depends_on: [TASK-002, TASK-003, TASK-004, TASK-005]
task_type: full-microservice
loop_count: 1
max_loops: 10
pr_url: https://github.com/Banking-PapeeteConsulting/banking-reliever/pull/37
---

# TASK-006 — PII-free anchor history projection and audit-trail query

## Context
Expose a **PII-free audit trail** of every anchor transition for
`CAP.SUP.001.AUD` (Audit & Traceability) and `CAP.SUP.001.RET`
(Beneficiary Rights — proof that a right was honoured). The projection
is by construction PII-free, so it survives `PSEUDONYMISED` events
without re-creating an Article-17 violation: the row that records the
PSEUDONYMISED transition itself is the **proof of GDPR fulfilment** for
that anchor.

This task closes the roadmap by completing the read side of the
capability — TASK-002 delivered the canonical-directory projection,
this delivers the audit history.

## Capability Reference
- Capability: Beneficiary Identity Anchor (BNK.RLVR.CAP.SUP.002.BEN)
- Zone: SUPPORT
- Governing FUNC ADR: ADR-BCM-FUNC-0016
- Strategic-tech anchors: ADR-TECH-STRAT-003 (REST), ADR-TECH-STRAT-004
  (dual referential access — synchronous QRY path), ADR-TECH-STRAT-007,
  ADR-TECH-STRAT-008
- Tactical stack: ADR-TECH-TACT-002

## What to Build
Extend the microservice to project `PRJ.SUP.002.BEN.ANCHOR_HISTORY` and
serve `QRY.SUP.002.BEN.GET_ANCHOR_HISTORY`.

1. **Projection** — `PRJ.SUP.002.BEN.ANCHOR_HISTORY` per
   `read-models.yaml` (process v0.2.0 with **explicit per-field
   sourcing** under `PRJ.ANCHOR_HISTORY.fed_by`). Append-only, one row
   per received RVT, keyed on `(internal_id, revision)`. Each column
   sources from the wire-format field declared in `fed_by`:
   `internal_id`, `revision`, `transition_kind`, `command_id`,
   `right_exercise_id` (only on PSEUDONYMISED transitions; null
   otherwise), `actor` (sourced from the **RVT envelope** `actor`
   typed object per `bus.yaml.publication.envelope.actor` — NOT
   re-captured at projection time; the kind/subject/on_behalf_of are
   already on the wire, set by the producer per
   `ADR-TECH-STRAT-003`), `occurred_at`. **No PII columns are
   materialised** — verifiable by SQL schema dump. If the RVT schema
   changes the source location of any field, the projection consumer
   must be updated in lockstep — the `fed_by` block is the contract.
2. **Projection consumer** — ingests every received
   `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` from
   `sup.002.ben-events` (or from the in-process domain event stream if
   the implementation chooses to materialise the history in the same
   transaction as the directory — both are acceptable per
   `read-models.yaml` consistency model).
3. **Query handler** — `GET /anchors/{internal_id}/history` per
   `api.yaml.getAnchorHistory`. Returns rows ordered by `revision`
   ascending. Supports `?since_revision=N` to filter to transitions
   strictly greater than `N`. ETag + `Cache-Control: max-age=0`
   (re-validation on every request — audit consumers need read-
   after-write semantics). `404 ANCHOR_NOT_FOUND` if no rows match the
   path parameter.
4. **Retention** — 7 years from `occurred_at`, configurable. A purge
   job (cron / scheduled task — implementation choice) removes rows
   older than the retention window. The PSEUDONYMISED row remains
   intact within the window — it IS the GDPR fulfilment proof.
5. **PII-free invariant** — schema-level: the `anchor_history` table
   has no `last_name`, `first_name`, `date_of_birth`, or
   `contact_details` column. A migration test verifies this.
6. **Survives pseudonymisation** — when a PSEUDONYMISED RVT arrives,
   the projection records the row like any other transition (the
   payload's PII fields are null and never get projected anywhere).
   Previous MINTED / UPDATED / ARCHIVED / RESTORED rows for the same
   `internal_id` are NOT mutated by the PSEUDONYMISED event — they
   never contained PII in the first place.

## Business Events to Produce
None — read-side only.

## Business Objects Involved
- `BNK.RLVR.OBJ.SUP.002.BENEFICIARY_RECORD` — observed; no PII materialised in
  the projection

## Event Subscriptions Required
- `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` (own emitted event) —
  consumed by the in-process projection consumer to feed
  `PRJ.ANCHOR_HISTORY`.

## Definition of Done
- [ ] PostgreSQL schema declares the `anchor_history` table with
      composite primary key `(internal_id, revision)` and the columns
      enumerated in `read-models.yaml` — and **only** those columns
      (no PII columns)
- [ ] Migration test asserts the schema has no `last_name`,
      `first_name`, `date_of_birth`, or `contact_details` column (the
      PII-free invariant is enforced structurally)
- [ ] Projection consumer ingests every emitted RVT and writes one row
      per `(internal_id, revision)`; idempotent on the composite key
      (duplicate RVT delivery — at-least-once — does not produce
      duplicate rows)
- [ ] `actor` is captured server-side from the JWT subject claim when
      the command is processed and propagated to the history row
- [ ] `right_exercise_id` populated on PSEUDONYMISED rows; null on all
      other transition kinds
- [ ] `GET /anchors/{internal_id}/history` returns rows ordered by
      `revision` ascending with the `AnchorHistory` shape from
      `api.yaml.getAnchorHistory`
- [ ] `?since_revision=N` filters to rows with `revision > N`
- [ ] `404 ANCHOR_NOT_FOUND` when no row matches the path parameter
- [ ] ETag honoured with `max-age=0` (re-validation on every request);
      `If-None-Match` returns `304` on match
- [ ] The PSEUDONYMISED row remains intact in the projection after the
      anchor is pseudonymised — `GET /history` continues to return the
      complete transition sequence, ending with the PSEUDONYMISED row
      bearing the `right_exercise_id`; this is the GDPR-fulfilment
      proof
- [ ] Retention purge job exists and is configured for 7 years from
      `occurred_at`; the retention window is configurable (env var or
      config file)
- [ ] A purge test demonstrates rows older than the retention window
      are removed and rows within the window are preserved
- [ ] No PII ever lands in the projection — even in error paths
      (verifiable by negative tests: feed the consumer a hand-crafted
      RVT with PII set and assert PII never reaches the
      `anchor_history` table)
- [ ] No write to `process/BNK.RLVR.CAP.SUP.002.BEN/`
- [ ] `pytest` suite covers: full-lifecycle history (5 transitions →
      5 rows), `since_revision` filtering, at-least-once idempotency
      on the composite key, ETag/304 path, retention purge, PII-free
      schema audit, PSEUDONYMISED survives
- [ ] If `CAP.SUP.001.AUD` and/or `CAP.SUP.001.RET` already have
      process models declared, note in the PR description that this
      task delivers the query they need; no schema change is required
      on those consumers

## Acceptance Criteria (Business)
An auditor querying `GET /anchors/{internal_id}/history` can replay the
complete lifecycle of any beneficiary anchor — mint, every update,
archive/restore cycles, and the terminal pseudonymisation — without ever
seeing PII. The PSEUDONYMISED row, with its `right_exercise_id`, is the
durable proof that the right-to-be-forgotten was honoured for that
beneficiary. Old rows are purged on the 7-year GDPR / AML floor without
operator intervention.

## Dependencies
- TASK-002 (mandatory — foundation; MINTED RVT must exist to project)
- TASK-003 (UPDATED RVT)
- TASK-004 (ARCHIVED / RESTORED RVTs)
- TASK-005 (PSEUDONYMISED RVT — needed for the audit-trail completeness
  test, and for the GDPR-fulfilment proof story)

## Open Questions
None blocking launch. The `ANCHOR_HISTORY` retention default (7y) is
fixed by the process model — roadmap OQ-3 (whether the DPO will require
shorter retention or periodic purge of `MINTED` / `UPDATED` rows) is a
**deferred governance** question for a future FUNC ADR + delta `/process`
pass; do NOT modify retention semantics from inside this task. If the
question is reactivated during implementation, surface it on the PR and
route it back through reliever-knowledge.
