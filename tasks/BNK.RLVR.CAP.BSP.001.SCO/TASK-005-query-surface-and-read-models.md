---
task_id: TASK-005
capability_id: BNK.RLVR.CAP.BSP.001.SCO
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Behavioural Score
epic: Epic 4 — Query surface & read-models
status: todo
priority: medium
depends_on: [TASK-003]
task_type: full-microservice
loop_count: 0
max_loops: 10
---

# TASK-005 — Query surface and event-sourced read-models

## Context
Per `ADR-TECH-STRAT-008` this capability is a multi-faceted information
producer — operational bus + analytical bus + synchronous REST query
surface. This task delivers the REST query face: `GET
/cases/{case_id}/score` (current view) and `GET
/cases/{case_id}/score-history`, backed by two event-sourced projections
fed by `BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED` and
`BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED`. Dashboards
(`BNK.RLVR.CAP.CHN.001.DSH`), prescriber views (`CAP.CHN.002.VUE`), and
arbitration (`BNK.RLVR.CAP.BSP.001.ARB`) can consume scoring state without
subscribing to the bus or polling the aggregate directly.

The projections are **eventually consistent** per
`read-models.yaml.consistency: eventual` — a `GET` issued milliseconds
after a recomputation may legitimately see the prior value. The
contract makes this explicit via the `ETag` + `PT5S max-age` cache
header on the current-score endpoint.

## Capability Reference
- Capability: Behavioural Score (BNK.RLVR.CAP.BSP.001.SCO)
- Zone: BUSINESS_SERVICE_PRODUCTION
- Governing FUNC ADR: ADR-BCM-FUNC-0005
- Strategic-tech anchors: ADR-TECH-STRAT-003 (REST), ADR-TECH-STRAT-004
  (dual referential access — REST is the synchronous path),
  ADR-TECH-STRAT-005 (OTel), ADR-TECH-STRAT-008 (multi-faceted producer)
- Tactical stack: ADR-TECH-TACT-003

## What to Build
Extend the microservice from TASK-003 (and optionally TASK-004 for the
`entry_score` field) to deliver the read side.

1. **Projection — `PRJ.BSP.001.SCO.CURRENT_SCORE_VIEW`** per
   `read-models.yaml`. Backs `BNK.RLVR.RES.BSP.001.CURRENT_SCORE`. Fed by
   `BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED` and
   `BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED`. Fields: `case_id`,
   `score_value`, `delta_score`, `computation_timestamp`,
   `model_version`, `last_evaluation_id`. One row per `case_id` —
   last-write-wins on the projection by `evaluation_id` (or by the
   stream offset, implementer choice; must be deterministic).
2. **Projection — `PRJ.BSP.001.SCO.SCORE_HISTORY`**. Append-only, one
   row per ingested RVT. Fields: `case_id`, `evaluation_id`,
   `score_value`, `delta_score`, `evenement_declencheur`,
   `computation_timestamp`. Retention 24 months (configurable purge job).
3. **Projection consumer** — subscribes to
   `bsp.001.sco-events` from inside the same process (or via a
   dedicated outbox-relay tail — implementer choice). For at-least-once
   delivery, the projection upserts are idempotent on `evaluation_id`
   (or on the composite `(case_id, evaluation_id)` for the history
   projection).
4. **Query `QRY.GET_CURRENT_SCORE`** — `GET
   /capabilities/bsp/001/sco/cases/{case_id}/score` per
   `api.yaml.getCurrentScore`. Reads from `PRJ.CURRENT_SCORE_VIEW`.
   Returns the `BeneficiaryScoreView` shape per the schema declared by
   the projection. ETag + `Cache-Control: max-age=5` (`PT5S`). `If-
   None-Match` honoured → `304`. `404` when no projection row exists
   for `case_id`.
5. **Query `QRY.LIST_SCORE_HISTORY`** — `GET
   /capabilities/bsp/001/sco/cases/{case_id}/score-history` per
   `api.yaml.listScoreHistory`. Query params: `since` (date, optional)
   and `limit` (integer, default 50, max 500). Reads from
   `PRJ.SCORE_HISTORY` in chronological order. `404` when no row
   exists for `case_id`. ETag honoured.
6. **Out-of-order protection** — if an RVT arrives whose
   `evaluation_id` (or `computation_timestamp`) is older than what the
   current-score projection already holds, the upsert is dropped
   (last-write-wins on the projection — never lose a later value to an
   earlier one). The history projection is append-only and tolerates
   any ordering.
7. **OTel** — every query is traced (p50/p95 latency tagged with the
   query id), and projection lag (consumer-position vs head of stream)
   is exposed as a metric per `ADR-TECH-STRAT-005`. Detailed dashboards
   are Epic 5; this task only emits the signals.
8. **No PII** — score payloads carry `case_id` only, never PII or
   `internal_id`. The query consumers (`BNK.RLVR.CAP.CHN.001.DSH`,
   `CAP.CHN.002.VUE`, `BNK.RLVR.CAP.BSP.001.ARB`) resolve identity separately
   against `BNK.RLVR.CAP.SUP.002.BEN`.
9. **Eventual-consistency contract** is documented explicitly in the
   OpenAPI of the two endpoints (e.g. a `Cache-Control: max-age=5`
   header + a `Last-Modified` header reflecting the
   `computation_timestamp` of the row served).

## Business Events to Produce
None — read-side only.

## Business Objects Involved
- `BNK.RLVR.OBJ.BSP.001.EVALUATION` — projected (without PII) into the two
  read-models

## Event Subscriptions Required
- `BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED` (own emitted event) — consumed by
  the in-process projection consumer to feed both projections
- `BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED` (own emitted event) — same

## Definition of Done
- [ ] PostgreSQL schema declares the two projection tables with
      composite primary keys: `current_score_view (case_id)` and
      `score_history (case_id, evaluation_id)`; matching the fields
      enumerated in `read-models.yaml`
- [ ] Projection consumer ingests every emitted RVT and updates both
      projections idempotently (duplicate delivery does not produce
      duplicate rows in the history projection, and does not regress
      the current-score projection)
- [ ] `GET /cases/{case_id}/score` returns the
      `PRJ.CURRENT_SCORE_VIEW` row with the shape declared in
      `read-models.yaml.QRY.GET_CURRENT_SCORE.response.fields`
- [ ] ETag honoured; `If-None-Match` matching returns `304`;
      `Cache-Control: max-age=5` (`PT5S`) per
      `api.yaml.getCurrentScore.cache`
- [ ] `404` when no projection row exists for `case_id`
- [ ] `GET /cases/{case_id}/score-history` returns chronological rows
      with the shape declared in
      `read-models.yaml.QRY.LIST_SCORE_HISTORY.response.item_fields`
- [ ] `since` (date, optional) filters rows whose
      `computation_timestamp >= since`; `limit` (default 50, max 500)
      caps the response
- [ ] `404` when no row exists for `case_id`
- [ ] Out-of-order RVT delivery never regresses `PRJ.CURRENT_SCORE_VIEW`
      — verified by integration test (deliver an older event after a
      newer one; the projection keeps the newer value)
- [ ] No PII / no `internal_id` in any response body or header
- [ ] OTel spans cover both query handlers and the projection
      consumer; metrics expose projection lag and query p50/p95
- [ ] 24-month retention purge job exists for `PRJ.SCORE_HISTORY` per
      `read-models.yaml.retention`; the retention window is
      configurable via env var
- [ ] Both endpoints are exercised by integration tests against three
      consumer shapes: `BNK.RLVR.CAP.CHN.001.DSH` (progression bar),
      `CAP.CHN.002.VUE` (prescriber timeline), `BNK.RLVR.CAP.BSP.001.ARB`
      (algorithmic vs override check) — verified by stub clients
      shipped in `tests/`
- [ ] No write to `process/BNK.RLVR.CAP.BSP.001.SCO/`

## Acceptance Criteria (Business)
A dashboard or prescriber view can render the beneficiary's current
score and their score history without subscribing to the bus or
polling the aggregate. A 304 response on a repeated read costs no
extra bandwidth. Audit / arbitration consumers can replay the
score chronology over the last 24 months and reconcile against the
events they have on the bus — the projection and the event stream
agree on every `evaluation_id`. The eventual-consistency contract is
documented and acceptable to the consumers — a 5-second freshness
window for current score, append-only history.

## Dependencies
- TASK-003 (Epic 2) — mandatory: `RVT.CURRENT_SCORE_RECOMPUTED` must
  be a real, schema-conforming payload for the projection to fold;
  `TASK-002`'s stub can substitute for local development but not for
  the final integration tests.

## Open Questions
None blocking launch. The optional `entry_score` field on the
`CURRENT_SCORE_VIEW` row is populated by `RVT.ENTRY_SCORE_COMPUTED`
once TASK-004 ships; until then, the field is null. The roadmap
explicitly allows Epic 4 to progress against a partially populated
projection — no need to gate this task on TASK-004.
