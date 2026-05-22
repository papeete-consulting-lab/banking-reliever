---
task_id: TASK-006
capability_id: BNK.RLVR.CAP.BSP.001.SCO
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Behavioural Score
epic: Epic 5 — Model versioning & operability hardening
status: todo
priority: low
depends_on: [TASK-005]
task_type: full-microservice
loop_count: 0
max_loops: 10
---

# TASK-006 — Model versioning, operability hardening, and contract harness

## Context
This task productionises the scoring service. Up to now (TASKs 003–005)
the capability runs with an implicit `model_version` baked into the
algorithm and minimal operational visibility. Per the roadmap risk
matrix, two risks demand explicit treatment before this capability is
trusted at production load: **scoring model version is changed in
production without governance review** (config-driven gating) and
**stub schemas drift from real payloads** (contract harness closes the
loop). This task also tunes snapshotting, stands up OpenTelemetry
dashboards, writes the DLQ runbook, and attaches the contract harness
that derives `openapi.yaml` and `asyncapi.yaml` from the process model
+ BCM corpus.

## Capability Reference
- Capability: Behavioural Score (BNK.RLVR.CAP.BSP.001.SCO)
- Zone: BUSINESS_SERVICE_PRODUCTION
- Governing FUNC ADR: ADR-BCM-FUNC-0005
- Governing GOV ADR: ADR-BCM-GOV-0002 (BCM arbitration board — gates
  `model_version` activation)
- Strategic-tech anchors: ADR-TECH-STRAT-001 (bus / Rule 3 outbox —
  snapshotting tuning preserves outbox guarantees), ADR-TECH-STRAT-005
  (OTel — primary unit of observability is the L2 capability),
  ADR-TECH-STRAT-008 (multi-faceted producer — contract harness
  formalises the wire face)
- Tactical stack: ADR-TECH-TACT-003

## What to Build
Five orthogonal hardening axes, kept as one task because none of them is
standalone-shippable without the others.

1. **Config-driven `model_version`** — the active scoring model version
   is read from configuration, not hard-coded. Changing the active
   version requires a deploy + an explicit GOV-0002 arbitration board
   sign-off (recorded in the PR description that promotes the new
   version). A "current" + "next" pair MAY be supported for canary
   evaluation — implementer choice; document the rollout strategy in
   the service README. `MODEL_VERSION_MISMATCH` (already declared as
   an error code in `commands.yaml.CMD.RECOMPUTE_SCORE`) is exercised
   end-to-end: ingesting an aggregate state from an incompatible
   prior version is rejected with `409`.
2. **Snapshotting tuning** — `aggregates.yaml.snapshotting` declares
   `strategy: every-N-events, n: 100`. Validate (or revise with
   rationale) — load-test the recomputation handler against the
   chosen `n`, measure cold-start replay time and write amplification,
   commit either "100 is correct because…" or a tuned value with the
   measurement that justified it. Reflect any chosen revision back as
   a TECH-TACT delta — the YAML stays owned by `/process`.
3. **OpenTelemetry dashboards** per `ADR-TECH-STRAT-005`. Dashboards
   live as code under `sources/BNK.RLVR.CAP.BSP.001.SCO/backend/observability/`
   (Grafana JSON, or the format the deployment platform uses) and
   expose at minimum: (a) recomputation rate per trigger kind
   (`TRANSACTION_AUTHORIZED`, `TRANSACTION_REFUSED`, `RELAPSE_SIGNAL`,
   `PROGRESSION_SIGNAL`); (b) threshold-crossing rate; (c) DLQ depth
   on each of the four subscription queues; (d) p50/p95 latency on
   `GET /cases/{case_id}/score` and `GET
   /cases/{case_id}/score-history`; (e) projection lag (head-of-stream
   vs current projection position) from TASK-005.
4. **DLQ runbook** — for each of the two flagged DLQ error codes in
   `policies.yaml.error_handling` (`AGGREGATE_NOT_INITIALISED`,
   `BENEFICIARY_UNKNOWN`), document the operational response:
   diagnosis steps, mitigation, escalation path. Lives in the service
   README under an explicit `## Runbook — Dead-Letter Queues` section.
5. **Contract harness** — invoke `/harness-backend BNK.RLVR.CAP.BSP.001.SCO` to
   scaffold the `*.Contracts.Harness/` project and emit
   `sources/BNK.RLVR.CAP.BSP.001.SCO/backend/contracts/specs/openapi.yaml` and
   `asyncapi.yaml` with full bidirectional `x-lineage` to `process/`
   and the BCM corpus. The harness becomes part of CI: every build
   re-derives the specs and asserts no operation / channel was
   removed without a deprecation marker. The two
   `app.MapGet("/openapi.yaml")` / `app.MapGet("/asyncapi.yaml")`
   endpoints are wired in the Presentation layer.

## Business Events to Produce
None — operability and hardening; no new events.

## Business Objects Involved
- `BNK.RLVR.OBJ.BSP.001.EVALUATION` — versioned by `model_version`; the
  contract carries the version on every emitted RVT (already in the
  RVT schemas from TASK-002 / TASK-003)

## Event Subscriptions Required
None — same surface as TASK-003 / TASK-005.

## Definition of Done
- [ ] `model_version` is sourced from configuration (env var or config
      file); changing it requires a deploy
- [ ] PR procedure for promoting a `model_version` documents an
      `ADR-BCM-GOV-0002` arbitration-board sign-off as a precondition;
      a check-list item in the PR template enforces it
- [ ] `MODEL_VERSION_MISMATCH` is exercised by integration test:
      ingest an aggregate state persisted under version A, activate
      version B, attempt to recompute → `409 MODEL_VERSION_MISMATCH`
- [ ] Snapshotting strategy validated against a load test (≥10× the
      expected steady-state throughput per `case_id`); the result is
      either "every-100-events is correct because…" or a revised
      `n` with the measurement attached; the chosen value is
      reflected in the service README
- [ ] OTel dashboards-as-code under
      `sources/BNK.RLVR.CAP.BSP.001.SCO/backend/observability/` exposing the
      five panels enumerated above; a `make dashboards` target (or
      equivalent) renders them locally for review
- [ ] DLQ runbook section in `sources/BNK.RLVR.CAP.BSP.001.SCO/backend/README.md`
      covers `AGGREGATE_NOT_INITIALISED` and `BENEFICIARY_UNKNOWN` —
      diagnosis, mitigation, escalation
- [ ] `/harness-backend BNK.RLVR.CAP.BSP.001.SCO` has been run; the
      `Contracts.Harness/` project exists; CI runs the harness on
      every build and fails on contract drift
- [ ] `contracts/specs/openapi.yaml` covers every operation in
      `api.yaml` with full `x-lineage` to `process/` and the BCM
- [ ] `contracts/specs/asyncapi.yaml` covers every channel in
      `bus.yaml` (publish + subscribe) with full `x-lineage`
- [ ] `GET /openapi.yaml` and `GET /asyncapi.yaml` endpoints serve
      the live specs from the running service
- [ ] No write to `process/BNK.RLVR.CAP.BSP.001.SCO/` from any of the five
      axes (the contract harness is the only step that reads
      `process/.../schemas/` programmatically — through `rlv-knowledge` and
      `/harness-backend`, never via direct authoring)

## Acceptance Criteria (Business)
A new scoring model version cannot be silently activated — the deploy
gate requires the GOV-0002 arbitration board to have signed off.
Operations can spot a regression (DLQ growth, threshold-crossing rate
anomaly, latency spike on the query endpoints) within seconds via the
OpenTelemetry dashboards. When a message ends up in a DLQ, the
runbook tells the operator what to do without paging an engineer. The
public contract of the capability (REST + bus) is served by the
running service itself and is provably aligned with the BCM corpus on
every build — drift can never reach a downstream consumer silently.

## Dependencies
- TASK-005 — mandatory: the contract harness derives `openapi.yaml`
  from the live query surface, which only exists after Epic 4 ships.
  Snapshotting tuning and OTel dashboards also need the read side to
  validate end-to-end signals.

## Open Questions
- [ ] **Score recomputation throughput targets** — the roadmap Open
      Question "Score recomputation throughput targets" flags that no
      NFRs are surfaced in `ADR-BCM-FUNC-0005`. Snapshotting tuning
      and queue capacity dimensioning need a target — e.g. expected
      recomputations / second at steady state and at peak. Elicit the
      number from the product owner / FUNC-0005 author before
      launching this task; otherwise the load test in DoD item 4 has
      no target to validate against.
