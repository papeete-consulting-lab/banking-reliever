---
task_id: TASK-006
capability_id: CAP.CHN.001.DSH
capability_name: Beneficiary Dashboard
epic: Epic 5 — Real-CORE handoff and operability hardening
status: todo
priority: low
depends_on: [TASK-002, TASK-003, TASK-004, TASK-005]
task_type: full-microservice
loop_count: 0
max_loops: 10
---

# TASK-006 — Real-CORE handoff and operability hardening

## Context
This task closes the dashboard's path to staging. Up to now (TASKs
002–005) the BFF binds to the upstream **stubs** of `CAP.BSP.001.SCO`,
`CAP.BSP.001.TIE`, and `CAP.BSP.004.ENV` — synthetic events with
contract-correct shape but no real domain truth. Epic 5 decommissions
those stubs in favour of real producers, hardens observability (OTel
dashboards, DLQ runbook, JWT actor enforcement against
`CAP.SUP.001.CON`), and validates the polling-vs-push economics under
realistic load. After this task, the capability ships to staging.

The hardening axes are kept as one task because none of them is
standalone-shippable without the others: dashboards need real signals
to be meaningful, the JWT enforcement needs real consent integration,
the polling validation needs real upstream traffic.

## Capability Reference
- Capability: Beneficiary Dashboard (CAP.CHN.001.DSH)
- Zone: CHANNEL
- Governing FUNC ADR: ADR-BCM-FUNC-0009
- Strategic-tech anchors: ADR-TECH-STRAT-001, ADR-TECH-STRAT-003
  (bi-layer security — channel + inter-service), ADR-TECH-STRAT-005
  (OTel — capability as primary observability unit), ADR-TECH-STRAT-006
  (Kubernetes, 4 environments, Day-0 GitOps), ADR-TECH-STRAT-008
- Tactical stack: ADR-TECH-TACT-001

## What to Build
Five orthogonal hardening axes, each measurable.

1. **Upstream handoff** — switch each of the three subscription
   bindings from the producer's stub exchange to its real-producer
   exchange. The exchange names do not change (per ADR-TECH-STRAT-001
   Rule 1 the exchange is owned by the capability, not the
   implementation); but the *traffic shape* changes (real volumes,
   real timing, real cardinality). Validate:
   - No functional regression on `GET /dashboard`,
     `GET /transactions`, `POST /dashboard-views`.
   - The aggregate's `INV.DSH.001..006` invariants continue to hold
     under real-traffic conditions.
   - Each producer's stub is documented as retired (or kept inert via
     `STUB_ACTIVE=false`) in its own capability — coordinate the
     decommission, do not delete upstream code from this task.
2. **OpenTelemetry dashboards-as-code** under
   `sources/CAP.CHN.001.DSH/bff/observability/` (Grafana JSON or the
   deployment platform's equivalent), exposing at minimum:
   - Subscription queue depth per upstream RVT (3 panels).
   - End-to-end latency: RVT received → aggregate updated → next
     `GET /dashboard` poll reflects the change.
   - 304 ratio on `GET /dashboard` and `GET /transactions` (target:
     ≥ 80 % at steady state).
   - `RVT.DASHBOARD_VIEWED` emission rate.
   - Debounce hit rate (`INV.DSH.004` — % of `POST /dashboard-views`
     that returned `VIEW_DEBOUNCED`).
3. **JWT actor enforcement bi-layer security** per
   `ADR-TECH-STRAT-003`. TASK-003 already added the channel-side
   check (JWT `sub` matches `case_id` owner); this task makes it
   robust:
   - The owner mapping comes from a real `CAP.SUP.001.CON` lookup
     (or its contract stub if `CAP.SUP.001.CON` is not yet shipped —
     coordinate via OQ-2 in the roadmap).
   - The consent claim shape is finalised and documented as a
     TECH-TACT delta (resolves the OQ-2 placeholder from TASK-003).
   - Integration test exercises a synthetic mismatched-`sub` token:
     the BFF returns `403 Forbidden` and never reaches the
     aggregate.
4. **DLQ runbook** under
   `sources/CAP.CHN.001.DSH/bff/README.md#runbook--dead-letter-queues`.
   `EVENT_ALREADY_PROCESSED` (`INV.DSH.002`) and `STALE_EVENT`
   (`INV.DSH.003`) are ack-and-drop by design — they never DLQ.
   The DLQ scenario is **out-of-spec payloads** (schema-validation
   failure on incoming RVTs). The runbook documents: diagnosis steps
   (inspect the DLQ message + the producer's recent schema commits),
   mitigation (drain the DLQ once the producer fix lands), escalation
   (open a `/fix` skill cycle on the producer).
5. **Polling-vs-push economics validation** — load-test at the
   `ADR-TECH-TACT-001` target shape:
   - 5 s polling cadence.
   - 100+ concurrent active dashboards on a single Kubernetes pod.
   - Target: 304 ratio ≥ 80 %, pod CPU < 50 %.
   - If the target is met: commit the measurement in the BFF's
     README as the steady-state evidence supporting the
     `simplicity-first` polling choice.
   - If NOT met: surface the gap as a TECH-TACT delta (widen
     `max_age` from PT5S, or introduce SSE) — this is a
     `simplicity-first` violation and requires
     `ADR-TECH-TACT-001` amendment. **Do not** silently change the
     polling cadence inside this task.

## Business Events to Produce
None — operability and hardening; no new events. The same single RVT
(`RVT.DASHBOARD_VIEWED`) from TASK-005 continues to flow, now under
real upstream traffic.

## Business Objects Involved
- `OBJ.BSP.002.PARTICIPATION` — same as TASK-002..005, now driven by
  real producer events

## Event Subscriptions Required
Same as TASK-002 — three upstream subscriptions, now bound to real
producer exchanges (which keep the same names; only the producers'
implementations swap from stub to real).

## Definition of Done
- [ ] **Upstream handoff verified**: integration test against the
      three real producers (`CAP.BSP.001.SCO` Flow B,
      `CAP.BSP.001.TIE` real tier engine, `CAP.BSP.004.ENV` real
      envelope engine) shows the aggregate populates end-to-end with
      no functional regression on the three HTTP endpoints. Each
      producer's stub is documented as retired in its own
      capability's stub README (coordination, not direct edit)
- [ ] **OTel dashboards-as-code** under
      `sources/CAP.CHN.001.DSH/bff/observability/` cover the five
      panels enumerated above; a `make dashboards` target (or the
      deployment platform's equivalent) renders them locally for
      review
- [ ] **JWT actor enforcement** integration test: synthetic
      mismatched-`sub` token → `403 Forbidden`; the request never
      reaches the aggregate; OTel trace records the rejection
- [ ] **Consent claim shape** resolved (closes OQ-2) and documented
      inline + as a TECH-TACT delta in the BFF README; the consent
      gate on the frontend reads the agreed claim and exits to the
      explanatory view when the claim is missing or revoked
- [ ] **DLQ runbook** present in
      `sources/CAP.CHN.001.DSH/bff/README.md` covering schema-
      validation failures on inbound RVTs (the only legitimate DLQ
      scenario for this capability)
- [ ] **Polling economics load test** at 100+ concurrent dashboards
      on one pod, 5 s cadence: result captured (304 ratio + CPU %).
      If targets met: numbers committed in the README. If not:
      TECH-TACT delta opened against `ADR-TECH-TACT-001` and a
      follow-up task referenced — but no silent cadence change
- [ ] **Contract harness via `/harness-backend`** OR an equivalent
      contract-validation step in CI that re-derives the OpenAPI +
      AsyncAPI surfaces of the BFF from `process/CAP.CHN.001.DSH/`
      on every build (note: `/harness-backend` is described as
      targeting non-CHANNEL zones in its skill description; if the
      tooling has not yet been extended to CHANNEL BFFs, surface the
      gap and ship a CI script that asserts the BFF's serialised
      routes match `api.yaml` and the emitted RVT matches
      `bus.yaml` — same intent, different mechanism). Either way:
      the public contract is provably aligned with `process/` on
      every build
- [ ] No write to `process/CAP.CHN.001.DSH/`

## Acceptance Criteria (Business)
The dashboard ships to staging with real upstream producers, real
consent enforcement, and an operations team that can spot regressions
within seconds via the OTel dashboards. A JWT belonging to a different
beneficiary cannot reach another's dashboard. Schema drift on an
upstream producer never silently propagates into the aggregate — it
lands in a DLQ with a documented runbook entry. The polling-vs-push
choice is no longer a hope but a measured outcome: either the
`simplicity-first` cadence holds under realistic load, or the gap is
explicitly opened as a TECH-TACT delta with the data to back it.

## Dependencies
- TASK-002, TASK-003, TASK-004, TASK-005 — the full functional
  surface of the dashboard must be in place before hardening; you
  cannot tune dashboards for endpoints that don't exist yet.
- Real upstream producers operational in dev — see Open Questions.

## Open Questions
- [ ] **Real upstream producers readiness — same as Epic 5's entry
      condition.** This task can only be launched when:
      (a) `CAP.BSP.001.SCO` Flow B is operational (CAP.BSP.001.SCO/TASK-003
      done — currently needs_info, blocked on AUT/SIG upstream + tier-
      cache policy);
      (b) `CAP.BSP.001.TIE` real tier engine is operational
      (TIE roadmap not yet authored — only the contract stub is done);
      (c) `CAP.BSP.004.ENV` real envelope engine is operational
      (ENV roadmap not yet authored — only the contract stub is done).
      Until all three land, this task stays parked. Coordinate via the
      `/implementation-pipeline` status report.
- [ ] **`CAP.SUP.001.CON` (Consent Management) readiness** — the
      bi-layer security check needs a real (or stub) consent
      authority. `CAP.SUP.001.CON` is not yet process-modelled. Until
      it is, the JWT actor check can be exercised against a hand-
      authored consent-claim shape, but the production path requires
      the upstream capability. Coordinate before staging ship.
- [ ] **Polling NFR target** — the 100+ concurrent dashboards / 80 %
      304 ratio / <50 % CPU triple is the roadmap's measurable
      target. If the load-testing harness available at this point
      cannot generate that profile, surface the gap before launching
      this task and either adapt the target or invest in the harness.
