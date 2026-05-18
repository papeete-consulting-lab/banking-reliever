---
task_id: TASK-001
capability_id: CAP.CHN.001.DSH
capability_name: Beneficiary Dashboard
epic: Epic 0 — Contract and Development Stub
status: done
priority: high
depends_on: []
task_type: contract-stub
loop_count: 0
max_loops: 10
superseded_by: TASK-002
superseded_reason: |
  Sequencing inversion — TASK-002 (Epic 1, real BFF foundation) shipped first
  (PR #17, in review on 2026-05-16). TASK-002 writes to the same canonical
  paths (sources/CAP.CHN.001.DSH/bff/ and sources/CAP.CHN.001.DSH/frontend/)
  with the production-shape implementation, which subsumes the canned stub
  this task would have produced. The decommissioning clause already baked
  into TASK-001's DoD ("the stub bundle's README states that the stub is
  retired once Epic 1 ships the real BFF foundation") is satisfied
  transitively: the real BFF + frontend serve the same contract surface
  with real data instead of canned data, so there is no consumer-visible
  regression and no remaining reason to scaffold the stub bundle.
---

> **Superseded on:** 2026-05-16 — closed as `done` by `/launch-task` after the user
> elected to skip scaffolding because PR #17 (TASK-002 real BFF + frontend) was
> already in flight on the same paths.

# TASK-001 — Contract and development stub for the Beneficiary Dashboard BFF + frontend

## Context
`CAP.CHN.001.DSH` is a CHANNEL-zone capability that exposes ONE emitted
resource event (`RVT.CHN.001.DASHBOARD_VIEWED` — telemetry) and a
three-operation HTTP surface (`POST /cases/{case_id}/dashboard-views`,
`GET /cases/{case_id}/dashboard`, `GET /cases/{case_id}/transactions`).
Per `ADR-BCM-URBA-0009` this capability owns the contract of both. As
long as the real BFF + frontend are not in place, this stub publishes the
contracted RVT with simulated values AND serves the three HTTP endpoints
with canned cold data, so downstream consumers — the analytical rail
(future `CAP.DAN.*`) on the bus side, and any external probe / dev
harness on the HTTP side — can develop in complete isolation.

Per `ADR-TECH-TACT-001` the CHANNEL stack is fixed: **.NET 10 Minimal
API BFF** under `sources/CAP.CHN.001.DSH/bff/` and **vanilla HTML5 /
CSS3 / JS frontend** under `sources/CAP.CHN.001.DSH/frontend/`. Stage 4
routes any `task_type: contract-stub` to a bundle that produces both
halves with canned data — the same agents (`create-bff` +
`code-web-frontend`) that will later carry the real implementation.

## Capability Reference
- Capability: Beneficiary Dashboard (CAP.CHN.001.DSH)
- Zone: CHANNEL
- Governing FUNC ADR: ADR-BCM-FUNC-0009
- Strategic-tech anchors: ADR-TECH-STRAT-001 (bus / Rule 2-4),
  ADR-TECH-STRAT-003 (REST / BFF / JWT / ETag),
  ADR-TECH-STRAT-004 (PII exclusion — low-PII lane),
  ADR-TECH-STRAT-007 (UUIDv7 envelope),
  ADR-TECH-STRAT-008 (multi-faceted producer)
- Tactical stack: ADR-TECH-TACT-001 (.NET 10 BFF + vanilla
  HTML5/CSS3/JS frontend, ETag + 5s polling, `localStorage` session,
  PII exclusion)

## What to Build
A runnable development stub spanning the BFF + the frontend, under the
canonical CHANNEL-zone layout:

1. **BFF stub** (`sources/CAP.CHN.001.DSH/bff/`):
   - On startup, declares the topic exchange `chn.001.dsh-events`
     (durable=true, owned by `CAP.CHN.001.DSH`) per `bus.yaml`.
   - Publishes synthetic `RVT.CHN.001.DASHBOARD_VIEWED` envelopes on the
     routing key
     `EVT.CHN.001.DASHBOARD_VIEWED.RVT.CHN.001.DASHBOARD_VIEWED` at a
     configurable cadence (default 1–10 events/min). Payloads validate
     against
     `process/CAP.CHN.001.DSH/schemas/RVT.CHN.001.DASHBOARD_VIEWED.schema.json`.
   - Carries the UUIDv7 envelope trio (`message_id`, `correlation_id` =
     synthetic `case_id`, `causation_id` = synthetic `client_request_id`)
     + `schema_version` semver per `ADR-TECH-STRAT-007` Rule 4.
   - Serves the three HTTP operations declared in `api.yaml`:
     - `POST /capabilities/chn/001/dsh/cases/{case_id}/dashboard-views`
       — first call returns `201 Created` and emits a
       `RVT.DASHBOARD_VIEWED` synchronously; second call within 30 s
       returns `200 VIEW_DEBOUNCED`; `400` on missing/invalid
       `case_id` or `client_request_id`. Debounce keyed on `case_id`
       (in-memory dict; resets on restart — acceptable for a stub).
     - `GET /capabilities/chn/001/dsh/cases/{case_id}/dashboard` —
       returns a canned `DashboardView` (current tier, score, open
       envelopes, `last_synced_at`) for known fixture `case_id`s; `404`
       for unknown IDs. ETag honoured; `Cache-Control: max-age=5`
       (PT5S); `If-None-Match` matching returns `304`.
     - `GET /capabilities/chn/001/dsh/cases/{case_id}/transactions?limit=N`
       — returns a canned `RecentTransactions` list (most-recent-first,
       bounded by `INV.DSH.005`: 50/30d) for known fixtures; `404`
       otherwise. ETag/304; `Cache-Control: max-age=5`. `limit`
       defaults to 20, max 50.
   - Activated / deactivated via `STUB_ACTIVE=true|false`.
   - Branch isolation per `CLAUDE.md`: exchange / port carry the branch
     slug.
2. **Frontend stub** (`sources/CAP.CHN.001.DSH/frontend/`):
   - A minimal vanilla HTML5/CSS3/JS shell that polls the canned BFF
     endpoints every 5 s, renders the dashboard chrome (tier panel +
     envelopes + recent transactions), and fires
     `POST /dashboard-views` on first paint + manual refresh.
   - French vocabulary throughout (per product vision); no English UI
     strings.
   - **Dignity rule materialised**: the DOM structure places the
     `#progression-section` (tier + score) **before** the
     `#restrictions-section` (envelope balances) — full DOM-order
     assertion deferred to TASK-003, but the structure must be correct
     from TASK-001.
   - `localStorage` carries a stable `client_request_id` (UUIDv7)
     across reloads so retries are idempotent.
3. **Self-validation** — every outgoing RVT payload AND every HTTP
   response body validates against its canonical schema before going
   out. The BFF's unit-test suite asserts schema conformance for each
   fixture, runnable in CI without bus / HTTP.

## Events to Stub
- `RVT.CHN.001.DASHBOARD_VIEWED` — published on `chn.001.dsh-events`
  with routing key
  `EVT.CHN.001.DASHBOARD_VIEWED.RVT.CHN.001.DASHBOARD_VIEWED`. Payload
  validates against
  `process/CAP.CHN.001.DSH/schemas/RVT.CHN.001.DASHBOARD_VIEWED.schema.json`.
  Synthetic emitter cycles across the optional payload variants
  (`current_tier_code` populated vs null, `current_score` populated vs
  null, with and without `client_context`).

## Query Operations to Stub
- `POST /capabilities/chn/001/dsh/cases/{case_id}/dashboard-views` —
  201 → emits one RVT; 200 `VIEW_DEBOUNCED` inside the 30 s window; 400
  on bad input.
- `GET /capabilities/chn/001/dsh/cases/{case_id}/dashboard` — returns
  the canned `DashboardView`; ETag/304; 404 for unknown `case_id`.
- `GET /capabilities/chn/001/dsh/cases/{case_id}/transactions?limit=N`
  — returns canned `RecentTransactions`; ETag/304; 404 for unknown
  `case_id`; `limit` capped at 50.

## Business Objects Involved
- `OBJ.BSP.002.PARTICIPATION` — carried by the dashboard view (as a
  synthesised, PII-free snapshot keyed by `case_id`)

## Required Event Subscriptions
None — the stub is a producer + HTTP server, not a consumer. The real
BFF (TASK-002) wires three upstream subscriptions; the stub does not.

## Definition of Done
- [ ] BFF stub source under `sources/CAP.CHN.001.DSH/bff/` (.NET 10
      Minimal API per `ADR-TECH-TACT-001`)
- [ ] Frontend stub source under `sources/CAP.CHN.001.DSH/frontend/`
      (vanilla HTML5/CSS3/JS — no framework, no CDN)
- [ ] `docker compose up` (or the project's equivalent) from the BFF
      folder starts the service + a local RabbitMQ; the frontend is
      served as static files on a separate dev port; branch-isolated
      port + exchange names per `CLAUDE.md`
- [ ] On startup the BFF declares the `chn.001.dsh-events` topic
      exchange (durable=true, owner=CAP.CHN.001.DSH)
- [ ] The synthetic emitter publishes `RVT.CHN.001.DASHBOARD_VIEWED`
      at 1–10 events/min on the canonical routing key; every payload
      validates against
      `process/CAP.CHN.001.DSH/schemas/RVT.CHN.001.DASHBOARD_VIEWED.schema.json`
      (covering both the no-snapshot variant and the populated-snapshot
      variant)
- [ ] Every emitted envelope carries UUIDv7 `message_id`,
      `correlation_id` (= synthetic `case_id`), `causation_id` (=
      synthetic `client_request_id`), `schema_version` semver
- [ ] `POST /cases/{case_id}/dashboard-views` accepts the canonical
      shape; first call returns 201 and triggers one synchronous RVT
      emission; second call within 30 s for the same `case_id` returns
      `200 VIEW_DEBOUNCED` and emits nothing; `400` on missing/invalid
      `case_id` or `client_request_id`
- [ ] `GET /cases/{case_id}/dashboard` returns canned PII-free
      `DashboardView` for known fixtures; ETag + `Cache-Control:
      max-age=5`; `If-None-Match` matching returns `304`; `404` for
      unknown `case_id`
- [ ] `GET /cases/{case_id}/transactions?limit=N` returns canned
      `RecentTransactions` (most-recent-first); ETag/304; `404` for
      unknown `case_id`; default limit 20, max 50
- [ ] At least 3 representative fixtures pre-seeded with stable
      `case_id` UUIDv7s (e.g. one fresh / empty-state, one mid-tier
      with non-empty envelopes, one with declined transactions —
      decline reason rendered semantically per the dignity rule)
- [ ] PII exclusion verified at the BFF response layer: no
      `last_name` / `first_name` / `date_of_birth` / raw contact-detail
      field in any canned response (negative test)
- [ ] Frontend shell polls `GET /dashboard` every 5 s, fires
      `POST /dashboard-views` on first paint, persists
      `client_request_id` in `localStorage`, renders the progression
      panel **before** the restrictions panel in the DOM (full
      DOM-order assertion deferred to TASK-003 but the structure must
      be correct)
- [ ] French vocabulary throughout the frontend (no English UI strings)
- [ ] `STUB_ACTIVE=false` halts BFF publication and short-circuits the
      HTTP endpoints to `503`
- [ ] Self-validation unit test asserts: every kind of outgoing
      payload validates against its canonical schema; the debounce
      invariant (`INV.DSH.004`) holds across two POST calls — runnable
      in CI without bus connectivity
- [ ] **Decommissioning** — the stub bundle's README states that the
      stub is retired once Epic 1 (TASK-002) ships the real BFF
      foundation and subscription bindings; further endpoints are
      phased out as TASK-003 / TASK-004 / TASK-005 deliver them
- [ ] No write to `process/CAP.CHN.001.DSH/` (read-only)

## Acceptance Criteria (Business)
A developer working on the analytical rail consumer (future
`CAP.DAN.*`) can bind a queue to `chn.001.dsh-events` and observe
validating `RVT.DASHBOARD_VIEWED` events. A frontend developer or QA
running the bundle locally can open the dashboard URL, see the
French-language progression-first layout populated from canned data,
trigger a refresh, observe the debounce on the second call, and load a
known fixture's transactions list. No dependency on the real BFF or on
upstream producer stubs; no schema-driven or contract-driven change is
needed when the real implementation lands later.

## Dependencies
None. Self-founding for the capability. The TASK-002+ real-implementation
tasks run in parallel with this stub and decommission it piece by
piece.

## Open Questions
None — `bus.yaml`, `api.yaml`, and the five JSON Schemas are on `main`
in v0.2.0 form. The CHANNEL stack and DOM-order rule are fixed by
ADR-TECH-TACT-001 and ADR-BCM-FUNC-0009.
