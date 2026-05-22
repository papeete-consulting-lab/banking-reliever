---
task_id: TASK-002
capability_id: BNK.RLVR.CAP.CHN.001.DSH
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Beneficiary Dashboard
epic: Epic 1 — BFF foundation, subscription bindings, dashboard aggregate
status: done
priority: high
depends_on: [BNK.RLVR.CAP.BSP.001.SCO/TASK-001, BNK.RLVR.CAP.BSP.001.TIE/TASK-001, CAP.BSP.004.ENV/TASK-001]
task_type: full-microservice
loop_count: 0
max_loops: 10
pr_url: https://github.com/Banking-PapeeteConsulting/banking-reliever/pull/17
---

> **Started on:** 2026-05-16
> **Submitted for review on:** 2026-05-16

# TASK-002 — BFF foundation, upstream subscriptions, and the dashboard aggregate

## Context
This task stands up the production-shape BFF and the frontend shell,
wires the three upstream subscriptions declared in
`process/BNK.RLVR.CAP.CHN.001.DSH/bus.yaml`, and materialises the
`AGG.CHN.001.DSH.BENEFICIARY_DASHBOARD` aggregate lazily on the first
incoming RVT for a given `case_id`. From this point on, every upstream
event (score recomputation, tier upgrade, envelope consumption) for a
known `case_id` lands in the BFF and updates the in-process aggregate —
even though the frontend chrome only displays an empty-state placeholder
until Epic 2 (TASK-003) renders the synthesised view.

The CHANNEL stack is fixed by `ADR-TECH-TACT-001`: .NET 10 Minimal API
BFF under `sources/BNK.RLVR.CAP.CHN.001.DSH/bff/`, vanilla HTML5/CSS3/JS frontend
under `sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/`. The aggregate IS the
projection — no separate read store — per the Framing Decisions section
of the roadmap.

## Capability Reference
- Capability: Beneficiary Dashboard (BNK.RLVR.CAP.CHN.001.DSH)
- Zone: CHANNEL
- Governing FUNC ADR: ADR-BCM-FUNC-0009
- Strategic-tech anchors: ADR-TECH-STRAT-001 (Rule 5 — consumer-owned
  queues on producer-owned exchanges; Rule 3 — outbox / at-least-once),
  ADR-TECH-STRAT-002 (modular monolith), ADR-TECH-STRAT-003 (REST /
  BFF / JWT), ADR-TECH-STRAT-004 (PII exclusion — low-PII lane),
  ADR-TECH-STRAT-005 (OTel — branch slug as `environment` tag),
  ADR-TECH-STRAT-007 (UUIDv7 envelope)
- Tactical stack: ADR-TECH-TACT-001 (.NET 10 BFF + vanilla
  HTML5/CSS3/JS frontend, ETag + 5s polling, PII exclusion)

## What to Build
The real BFF + frontend bundle implementing the consumption layer +
aggregate, plus an empty-state-capable frontend shell.

1. **Aggregate** — `AGG.CHN.001.DSH.BENEFICIARY_DASHBOARD` (one
   instance per `case_id`) with the state declared in
   `process/BNK.RLVR.CAP.CHN.001.DSH/aggregates.yaml`. State fields:
   `case_id` (identity), `current_tier_code`, `tier_upgraded_at`,
   `current_score`, `score_recomputed_at`, `open_envelopes` (list),
   `recent_transactions` (bounded list — populated by this task,
   surfaced as a query in TASK-004), `last_viewed_at` (populated by
   TASK-005), `last_processed_event_ids` (bounded set, idempotency).
   Lazy materialisation on first accepted command (`INV.DSH.006`).
2. **Three subscription bindings** — the BFF declares three
   consumer-owned queues bound to the producers' topic exchanges per
   `process/BNK.RLVR.CAP.CHN.001.DSH/bus.yaml.subscriptions`:
   - `chn.001.dsh.q.score-recomputed` on `bsp.001.sco-events` with
     binding pattern
     `BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED.BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED`
     — consumed by `POL.ON_SCORE_RECOMPUTED` → issues
     `CMD.SYNCHRONIZE_SCORE`.
   - `chn.001.dsh.q.tier-upgraded` on `bsp.001.tie-events` with
     binding pattern
     `BNK.RLVR.EVT.BSP.001.TIER_UPGRADED.BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED` —
     consumed by `POL.ON_TIER_UPGRADE_RECORDED` → issues
     `CMD.SYNCHRONIZE_TIER`.
   - `chn.001.dsh.q.envelope-consumed` on `bsp.004.env-events` with
     binding pattern
     `EVT.BSP.004.ENVELOPE_CONSUMED.RVT.BSP.004.CONSUMPTION_RECORDED`
     — consumed by `POL.ON_ENVELOPE_CONSUMPTION_RECORDED` → issues
     `CMD.RECORD_ENVELOPE_CONSUMPTION`.
   Queue names carry the branch slug per the worktree-isolation
   invariant in `CLAUDE.md`.
3. **Three reactive policies** — each policy validates the inbound
   payload against the upstream's published schema in `process/CAP.BSP.*/schemas/`,
   maps it to a homogeneous internal command, and applies the
   error-handling rules from `process/BNK.RLVR.CAP.CHN.001.DSH/policies.yaml`:
   `EVENT_ALREADY_PROCESSED` → ack-and-drop (idempotency);
   `STALE_EVENT` → ack-and-drop (out-of-order delivery is expected);
   payload-shape errors → DLQ for investigation.
4. **Three SYNCHRONIZE_* command handlers** — apply the inbound
   transition to the aggregate atomically, enforcing `INV.DSH.001`
   (PII exclusion — refuse to ingest any field whose schema-level
   `pii_classification` is `medium` / `high`), `INV.DSH.002`
   (idempotency on upstream `event_id`, 30-day bounded set),
   `INV.DSH.003` (monotonic timestamps — reject if
   `trigger.*_at` < locally-observed `*_at`). For
   `RECORD_ENVELOPE_CONSUMPTION`, also enforce `INV.DSH.005`
   (`recent_transactions` bounded at 50 / 30 d, FIFO eviction on
   `recorded_at`).
5. **Frontend shell** — minimal vanilla HTML5/CSS3/JS app that:
   - Polls `GET /capabilities/chn/001/dsh/cases/{case_id}/dashboard`
     every 5 s with `If-None-Match` honoured.
   - On `200`, renders an **empty-state placeholder** ("Première
     synchronisation en cours…" or equivalent) since the synthesised
     view itself is delivered by TASK-003.
   - On `404` (aggregate not yet materialised), renders the same
     placeholder — never surfaces a raw 404 to the user.
   - DOM structure already in place: `#progression-section` precedes
     `#restrictions-section` (assertion deferred to TASK-003).
   - JWT bearer token attached to every request (sourced from the host
     page / dev harness).
6. **OpenTelemetry** — traces span the inbound RVT → policy → command
   → aggregate path; the `environment` tag carries the branch slug per
   `ADR-TECH-STRAT-005`. Metric counters expose per-policy ingest rate
   and per-subscription DLQ depth (full dashboards are Epic 5).
7. **Branch isolation** — exchange names, queue names, BFF port,
   frontend dev port, RabbitMQ vhost (if any) all carry the branch
   slug per the worktree-isolation rule in `CLAUDE.md`.

## Business Events to Produce
None in this task. The single emitted RVT
(`BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED`) is the responsibility of Epic 4
(TASK-005). Epic 1 only consumes upstream events.

## Business Objects Involved
- `OBJ.BSP.002.PARTICIPATION` — referenced (PII-free) by the
  dashboard aggregate, keyed on `case_id`

## Event Subscriptions Required
- `BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED` (from `BNK.RLVR.CAP.BSP.001.SCO` via
  `bsp.001.sco-events`) — consumed by `POL.ON_SCORE_RECOMPUTED` to
  apply `CMD.SYNCHRONIZE_SCORE`
- `BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED` (from `BNK.RLVR.CAP.BSP.001.TIE` via
  `bsp.001.tie-events`) — consumed by `POL.ON_TIER_UPGRADE_RECORDED`
  to apply `CMD.SYNCHRONIZE_TIER`
- `RVT.BSP.004.CONSUMPTION_RECORDED` (from `CAP.BSP.004.ENV` via
  `bsp.004.env-events`) — consumed by
  `POL.ON_ENVELOPE_CONSUMPTION_RECORDED` to apply
  `CMD.RECORD_ENVELOPE_CONSUMPTION`

## Definition of Done
- [ ] BFF source under `sources/BNK.RLVR.CAP.CHN.001.DSH/bff/` (.NET 10
      Minimal API, MassTransit/RabbitMQ client, in-process aggregate
      store) — runnable via `dotnet run`
- [ ] Frontend shell under `sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/`
      (vanilla HTML5/CSS3/JS) — served on a branch-isolated dev port
- [ ] On startup the BFF declares the three queues exactly as
      enumerated in `process/BNK.RLVR.CAP.CHN.001.DSH/bus.yaml.subscriptions`;
      queue names carry the branch slug
- [ ] Each inbound payload is validated against the upstream
      capability's published JSON Schema (under
      `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/`,
      `process/BNK.RLVR.CAP.BSP.001.TIE/schemas/`,
      `process/CAP.BSP.004.ENV/schemas/`); malformed payloads land in
      the DLQ with a structured error
- [ ] Aggregate is lazily materialised on the first accepted command
      for a `case_id` (`INV.DSH.006`)
- [ ] `INV.DSH.001` (PII exclusion) — the policy refuses to ingest
      any upstream field tagged `pii_classification: medium | high`;
      negative test ingests a hand-crafted payload with a PII field
      and asserts the projection never carries it
- [ ] `INV.DSH.002` (idempotency) — the bounded
      `last_processed_event_ids` set drops duplicate `event_id` from
      any of the three channels; integration test replays the same
      RVT twice and asserts the aggregate transitions exactly once
- [ ] `INV.DSH.003` (monotonicity) — a `SYNCHRONIZE_SCORE` with
      `trigger.recomputed_at < score_recomputed_at` is ack-and-dropped
      (no state mutation, no DLQ); same for `SYNCHRONIZE_TIER`
- [ ] `INV.DSH.005` (recent_transactions bounded) — feeding 100
      synthetic `CONSUMPTION_RECORDED` events for one `case_id`
      leaves at most 50 entries in `recent_transactions`; entries
      older than 30 d are evicted (the surfacing endpoint comes in
      TASK-004)
- [ ] `GET /capabilities/chn/001/dsh/cases/{case_id}/dashboard`
      responds `404` when no aggregate exists for `case_id`, and
      responds `200` with a partial (mostly null) snapshot once the
      aggregate has been materialised by any of the three policies
- [ ] Frontend shell polls every 5 s, honours ETag (most responses
      after the first are `304`), renders the empty-state placeholder
      in French on both `200`-with-null-fields and `404`
- [ ] OpenTelemetry traces span inbound RVT → policy → command →
      aggregate path; the `environment` tag carries the branch slug
- [ ] Branch isolation: exchange / queue / port names carry the
      branch slug; two parallel worktrees can run concurrently
      without colliding on RabbitMQ resources
- [ ] No write to `process/BNK.RLVR.CAP.CHN.001.DSH/` (read-only)
- [ ] If a `sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/` stub from TASK-001 is
      present, its README is updated to note that the subscription
      bindings and aggregate materialisation are now served by the
      real BFF; the stub's HTTP endpoints stay runnable for the
      still-unimplemented views (TASK-003..005) until each is
      replaced
- [ ] Integration test corpus drives synthetic RVTs (one per
      channel, plus duplicates and out-of-order variants) and
      asserts: aggregate materialised; PII exclusion; idempotency;
      monotonicity; recent_transactions bound

## Acceptance Criteria (Business)
With this task in place, a developer running the BFF locally (in a
branch-isolated worktree) and pointing it at the three upstream
contract stubs (`BNK.RLVR.CAP.BSP.001.SCO`, `BNK.RLVR.CAP.BSP.001.TIE`,
`CAP.BSP.004.ENV` — all `TASK-001 done` on `main`) observes the
dashboard aggregate populate end-to-end as synthetic events flow.
Opening the dashboard URL shows the French empty-state placeholder
that gracefully transitions when the synthesised view ships in
TASK-003. No PII ever enters the aggregate; duplicate or out-of-order
upstream events are silently absorbed. The BFF survives a restart
without losing its outbox guarantees (snapshotting every 100 events
per `aggregates.yaml.snapshotting`).

## Dependencies
- `BNK.RLVR.CAP.BSP.001.SCO/TASK-001` — upstream contract stub (✅ done,
  PR #2): supplies `RVT.CURRENT_SCORE_RECOMPUTED`.
- `BNK.RLVR.CAP.BSP.001.TIE/TASK-001` — upstream contract stub (✅ done,
  PR #1): supplies `RVT.TIER_UPGRADE_RECORDED`.
- `CAP.BSP.004.ENV/TASK-001` — upstream contract stub (✅ done,
  PR #6): supplies `RVT.CONSUMPTION_RECORDED`.

All three are merged on `main` as of 2026-05-16 — the entry-condition
gate for Epic 1 is fully met today.

## Open Questions
None. The roadmap explicitly closes OQ-4 (mobile vs web) — one
frontend, mobile-first, vanilla JS, per `ADR-TECH-TACT-001`. The
case-opened eager-materialisation question (`open_question` in
`aggregates.yaml.INV.DSH.006`) is documented but deferred to a future
delta `/process` pass; for v0.2.0 the lazy-materialisation choice
stands and this task implements it.
