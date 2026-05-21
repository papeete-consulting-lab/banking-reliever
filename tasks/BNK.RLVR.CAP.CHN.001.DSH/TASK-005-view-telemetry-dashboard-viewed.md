---
task_id: TASK-005
capability_id: BNK.RLVR.CAP.CHN.001.DSH
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Beneficiary Dashboard
epic: Epic 4 — View telemetry — POST /dashboard-views emits BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED
status: todo
priority: medium
depends_on: [TASK-003]
task_type: full-microservice
loop_count: 0
max_loops: 10
---

# TASK-005 — View telemetry: POST /dashboard-views emits BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED

## Context
This task closes the analytics loop. The frontend signals to the BFF
every dashboard open or refresh; the BFF debounces them per `case_id`
(30 s) and emits the capability's **single domain event** —
`BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED` — so the analytical rail (future
`CAP.DAN.*`) can build engagement reports. Per `ADR-TECH-STRAT-001`
Rule 3 the emission goes through a transactional outbox; per Rule 4
business events appear only as routing-key prefixes — no autonomous
`EVT.*` message is published.

Epic 4 is independent of Epic 3 (TASK-004 transactions feed) — both
extend Epic 2's synthesised view in different directions and can run
in parallel.

## Capability Reference
- Capability: Beneficiary Dashboard (BNK.RLVR.CAP.CHN.001.DSH)
- Zone: CHANNEL
- Governing FUNC ADR: ADR-BCM-FUNC-0009
- Strategic-tech anchors: ADR-TECH-STRAT-001 (Rule 3 — outbox /
  at-least-once; Rule 4 — UUIDv7 envelope), ADR-TECH-STRAT-003 (REST /
  JWT), ADR-TECH-STRAT-004 (PII exclusion — `INV.DSH.001` extends to
  the wire payload), ADR-TECH-STRAT-007 (UUIDv7), ADR-TECH-STRAT-008
  (multi-faceted producer — operational rail emission + analytical
  rail CDC fan-out downstream)
- Tactical stack: ADR-TECH-TACT-001

## What to Build
1. **Command — `CMD.RECORD_DASHBOARD_VIEW`**: `POST
   /capabilities/chn/001/dsh/cases/{case_id}/dashboard-views` per
   `process/BNK.RLVR.CAP.CHN.001.DSH/api.yaml.recordDashboardView`. Body
   validates against
   `process/BNK.RLVR.CAP.CHN.001.DSH/schemas/CMD.CHN.001.DSH.RECORD_DASHBOARD_VIEW.schema.json`.
   Requires `client_request_id` (UUIDv7 — idempotency anchor, 5-minute
   window).
2. **Debounce (`INV.DSH.004`)** — keyed on `case_id`:
   - If `last_viewed_at` is null OR `now - last_viewed_at >= 30 s`:
     accept, update `last_viewed_at = now`, emit
     `RVT.DASHBOARD_VIEWED`, return `201 Created`.
   - Else: idempotent no-op — return `200 VIEW_DEBOUNCED`, emit
     nothing.
   - Idempotency on `client_request_id` (5-minute window): a duplicate
     `client_request_id` in either path returns the prior outcome
     (`201` or `200`) without re-emitting and without re-updating
     `last_viewed_at`.
3. **Transactional outbox emission** — when the debounce window is
   passed, the BFF persists an outbox row in the same transaction as
   the aggregate's `last_viewed_at` update (`ADR-TECH-STRAT-001`
   Rule 3 at-least-once). The relay publishes the RVT on exchange
   `chn.001.dsh-events` with routing key
   `BNK.RLVR.EVT.CHN.001.DASHBOARD_VIEWED.BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED`.
4. **Payload shape** — conforms to
   `process/BNK.RLVR.CAP.CHN.001.DSH/schemas/BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED.schema.json`:
   - Required: `event_id` (the resource event's identifier — the
     downstream idempotency anchor), `occurred_at` (server-side
     wall-clock when the BFF accepted the underlying
     `RECORD_DASHBOARD_VIEW` command), `case_id` (correlation key —
     opaque participation identifier).
   - Optional snapshot fields: `current_tier_code`, `current_score`
     (the values displayed at the moment of consultation; null when
     the aggregate has not yet received the corresponding upstream
     event).
   - Optional `client_context`: `app_version`, `device_class`
     (semantic labels only — no device fingerprint, no PII).
5. **Envelope** — UUIDv7 `message_id`, `correlation_id = case_id`,
   `causation_id = client_request_id`, `schema_version` semver per
   `ADR-TECH-STRAT-007` Rule 4.
6. **PII exclusion (`INV.DSH.001`) at the wire layer** — the schema's
   `additionalProperties: false` plus the absence of any PII-typed
   field guarantee the wire format stays PII-free. The
   identity-resolution path stays delegated to consumers via
   `BNK.RLVR.CAP.SUP.002.BEN`.
7. **Frontend integration** — the vanilla-JS shell fires
   `POST /dashboard-views` on:
   - First paint of the dashboard view (after the `200` from
     `GET /dashboard`).
   - Each manual pull-to-refresh / refresh button click.
   `localStorage` persists the `client_request_id` UUIDv7 across
   reloads so an accidental retry (browser refresh, network glitch)
   is idempotent.
8. **OTel** — emission rate metric + debounce hit rate metric
   (`emitted` / `debounced` counters tagged with `case_id` hash for
   privacy).

## Business Events to Produce
- `BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED` — emitted when an accepted
  `CMD.RECORD_DASHBOARD_VIEW` falls outside the 30 s debounce window
  for its `case_id`. Routing key
  `BNK.RLVR.EVT.CHN.001.DASHBOARD_VIEWED.BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED` on
  exchange `chn.001.dsh-events`. Carries the post-debounce snapshot
  fields (`current_tier_code`, `current_score`) when populated;
  `client_context` block when the frontend supplies it.

## Business Objects Involved
- `OBJ.BSP.002.PARTICIPATION` — carried by the RVT (as a PII-free
  snapshot keyed by `case_id`)

## Event Subscriptions Required
None new — telemetry is producer-side only.

## Definition of Done
- [ ] `POST /capabilities/chn/001/dsh/cases/{case_id}/dashboard-views`
      accepts requests, validates against
      `process/BNK.RLVR.CAP.CHN.001.DSH/schemas/CMD.CHN.001.DSH.RECORD_DASHBOARD_VIEW.schema.json`
- [ ] First call (or first call after 30 s) returns `201 Created` and
      triggers exactly one outbox row → one published RVT
- [ ] Second call within 30 s for the same `case_id` returns
      `200 VIEW_DEBOUNCED` with no outbox row, no published RVT
- [ ] **Idempotency on `client_request_id`** (5-minute window): a
      duplicate request returns the prior outcome with no second
      emission, no second outbox row; integration test exercises both
      the 201 → 201-replay path and the 200 → 200-replay path
- [ ] **`INV.DSH.004` end-to-end test**: open the dashboard twice
      within 5 s → exactly one RVT on the bus
- [ ] Emitted payload validates against
      `process/BNK.RLVR.CAP.CHN.001.DSH/schemas/BNK.RLVR.RVT.CHN.001.DASHBOARD_VIEWED.schema.json`,
      including the optional-fields variants (snapshot null vs
      populated, `client_context` absent vs present)
- [ ] Envelope carries UUIDv7 `message_id`, `correlation_id = case_id`,
      `causation_id = client_request_id`, `schema_version` semver
- [ ] **PII exclusion** at the wire layer — schema linter asserts
      `additionalProperties: false` in the RVT schema and the absence
      of any PII-typed field; negative test injects a hand-crafted
      payload with a PII field and asserts the emission path refuses
      to serialise it
- [ ] **Frontend integration** — the vanilla-JS shell fires
      `POST /dashboard-views` on first paint and on manual refresh;
      `localStorage` carries `client_request_id` across reloads
- [ ] **End-to-end Playwright test**: open the dashboard once →
      exactly one RVT on the bus; refresh inside 30 s → still exactly
      one RVT; refresh after 30 s → two RVTs total
- [ ] OTel emission rate and debounce hit rate metrics exposed
- [ ] If the TASK-001 stub is still running, its
      `POST /dashboard-views` endpoint is now shadowed; decommissioning
      note updated (the stub's debounce-and-emit was a synthetic
      simulation; this task ships the real one)
- [ ] No write to `process/BNK.RLVR.CAP.CHN.001.DSH/`

## Acceptance Criteria (Business)
Every intentional dashboard consultation by a beneficiary materialises
exactly one `RVT.DASHBOARD_VIEWED` on the bus — the basis of all
engagement analytics on the analytical rail. Background polling and
tab-refocus accidents never spam the bus thanks to the server-side
30 s debounce. Browser refreshes / network retries are idempotent
thanks to `client_request_id`. The wire payload carries the
beneficiary's tier and score at the moment of consultation (so
analytics can correlate engagement with progression) but **never**
PII — the privacy boundary holds at the wire format.

## Dependencies
- TASK-003 — the synthesised view must exist for the frontend's
  first-paint trigger to make sense (the frontend only fires
  `POST /dashboard-views` after a successful `GET /dashboard`).
  Epic 4 is **independent of Epic 3** (TASK-004 transactions feed) —
  both extend TASK-003 in parallel.

## Open Questions
None blocking launch. The downstream consumer (future `CAP.DAN.*` —
data analytics — engagement telemetry) is not yet declared in the
BCM (`consumers_open_question` block in `bus.yaml`). This is
expected and harmless on RabbitMQ topic exchanges: the routing key
is published, no queue is bound, no message is dropped because of
the absence of a consumer. When `CAP.DAN.*` ships its first
consumer, no change to this task is required.
