# Roadmap — Behavioural Scoring (BNK.RLVR.CAP.BSP.001.SCO)

## Capability Summary
> Compute the beneficiary's behavioural score in real time from each transaction and incoming behavioural signal. The score is the sole source of truth for tier-change decisions, except for explicitly validated prescriber overrides. The capability owns three resource events (`ENTRY_SCORE_COMPUTED`, `CURRENT_SCORE_RECOMPUTED`, `SCORE_THRESHOLD_REACHED`), one aggregate (`AGG.SCORE_OF_BENEFICIARY`, one instance per `case_id`), two read-models (current view + history), and the contracts of every event it emits.

## Strategic Alignment
- **Service offer**: Reliever's behavioural score is the core differentiating signal driving tier transitions, dashboard motivation, and arbitration. Core-domain capability (`coordinates: x=0.95, y=0.90` in `ADR-BCM-FUNC-0005`).
- **L1 strategic capability**: `CAP.BSP.001` — Behavioural Remediation
- **BCM Zone**: `BUSINESS_SERVICE_PRODUCTION`
- **Governing FUNC ADRs**:
  - `ADR-BCM-FUNC-0005` — *L2 Breakdown of CAP.BSP.001*
  - `ADR-BCM-FUNC-0016` (referenced) — relocates the beneficiary anchor from `CAP.REF.001.BEN` (REFERENTIAL) to `BNK.RLVR.CAP.SUP.002.BEN` (SUPPORT). Identity-resolution callers of this capability follow the new path.
- **Strategic-tech anchors**:
  - `ADR-TECH-STRAT-001` — Dual-Rail Event Infrastructure (operational rail = RabbitMQ; analytical rail = Kafka, fed downstream of the same PostgreSQL outbox via CDC; resource events carry the message, business events appear only as routing-key prefix)
  - `ADR-TECH-STRAT-002` — Microservice runtime, modular monolith per zone
  - `ADR-TECH-STRAT-003` — API contract strategy (REST/HTTP, JWT-borne actor identity)
  - `ADR-TECH-STRAT-004` — Data & referential layer (PII governance; producer never embeds canonical internal_id)
  - `ADR-TECH-STRAT-005` — Observability via OpenTelemetry with L2 as the primary unit
  - `ADR-TECH-STRAT-007` — Two-world identifier strategy (`case_id` is a UUIDv7 minted upstream by `CAP.BSP.002.ENR`; the bus envelope carries `message_id` / `correlation_id` / `causation_id` as UUIDv7; consumers resolve to canonical `internal_id` of `BNK.RLVR.OBJ.SUP.002.BENEFICIARY_RECORD` via `BNK.RLVR.CAP.SUP.002.BEN`)
  - `ADR-TECH-STRAT-008` — Capability as multi-faceted information producer (operational bus + analytical CDC + REST read APIs)
- **Tactical stack**: `ADR-TECH-TACT-003` — Python / FastAPI / PostgreSQL / RabbitMQ (operational rail) / Kafka (analytical rail, downstream of the outbox via CDC). Stage 4 routes to `implement-capability-python`.
- **Governing URBA**: `ADR-BCM-URBA-0003`, `0007`, `0008`, `0009`, `0010` (capability-as-responsibility, event meta-model, two-level event modelling, complete capability definition, L2 as urbanisation pivot).

## Framing Decisions

- **Contract-first delivery.** Per `ADR-BCM-URBA-0009`, this capability owns the wire contract of every event it emits. The first deliverable is therefore the JSON Schemas of the three RVTs (`ENTRY_SCORE_COMPUTED`, `CURRENT_SCORE_RECOMPUTED`, `SCORE_THRESHOLD_REACHED`) and a runnable development stub publishing them on the agreed bus topology, so that consumers (`BNK.RLVR.CAP.BSP.001.TIE`, `BNK.RLVR.CAP.BSP.001.ARB`, `BNK.RLVR.CAP.CHN.001.DSH`, `CAP.CHN.002.VUE`) can develop against a frozen interface.
- **Producer-owned stubs.** The development stub belongs to this capability's roadmap. It is decommissioned by this capability when the real algorithm lands, without coordination from consumers.
- **Two flows are first-class.**
  - *Flow A — Entry score baseline*: one-shot baseline at enrolment, materialises `RVT.ENTRY_SCORE_COMPUTED`.
  - *Flow B — Continuous recomputation*: every behavioural trigger (transaction authorised/refused, relapse/progression signal) re-evaluates the score, materialises `RVT.CURRENT_SCORE_RECOMPUTED`, and *atomically* materialises `RVT.SCORE_THRESHOLD_REACHED` when a tier boundary is crossed (invariant `INV.SCO.003`).
- **Atomic threshold detection (provisional).** The process model picks the same-transaction option for threshold detection — one trigger → 1 or 2 paired resource events, never one without the other. Alternative (separate observer reacting to `CURRENT_SCORE_RECOMPUTED`) remains an open question; flagged below.
- **No business event on the bus.** Per `ADR-TECH-STRAT-001` Rule 2, business events (`EVT.SCORE_RECOMPUTED`, `EVT.SCORE_THRESHOLD_REACHED`) appear only as the routing-key prefix; only resource events generate autonomous messages.
- **UUIDv7 envelope on every bus message.** Per `ADR-TECH-STRAT-007` Rule 4, each emitted RVT carries a fresh `message_id` (UUIDv7), a `correlation_id` set to `case_id`, and a `causation_id` set to the upstream `trigger.event_id` (or the HTTP request_id for back-channel calls). The stub and the real handler must both conform.
- **Idempotency-by-causation.** Each `RECOMPUTE_SCORE` is keyed by `trigger.event_id` (UUIDv7) with a 30-day window; entry score is keyed by `case_id` (UUIDv7) for its lifetime.
- **Identity-resolution delegated, not embedded.** Per `ADR-TECH-STRAT-004` + `ADR-TECH-STRAT-007`, this capability never carries the canonical `internal_id` of the beneficiary; consumers resolve `case_id` → `BNK.RLVR.OBJ.SUP.002.BENEFICIARY_RECORD.internal_id` via `BNK.RLVR.CAP.SUP.002.BEN` (post-rezone per `ADR-BCM-FUNC-0016`).
- **Analytical rail out of scope here.** The Kafka data-product facet is fed downstream of the same PostgreSQL transactional outbox via CDC (`ADR-TECH-STRAT-001` + `ADR-TECH-STRAT-008`) — this roadmap covers the operational rail and the REST surface only; the CDC topology is a cross-cutting `DAT.001` concern.

---

## Implementation Epics

### Epic 1 — Contract & Development Stub (extension)
**Goal**: Freeze the wire contract of `BNK.RLVR.CAP.BSP.001.SCO` by validating against the JSON Schemas for all three resource events (`ENTRY_SCORE_COMPUTED`, `CURRENT_SCORE_RECOMPUTED`, `SCORE_THRESHOLD_REACHED`) — now all present under `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/` since v0.2.0 of the model — and a development stub publishing them on the agreed RabbitMQ topology with the UUIDv7 envelope, so every downstream consumer can develop in isolation.

**Entry condition**: `process/BNK.RLVR.CAP.BSP.001.SCO/` v0.2.0 is on `main` (already met) and the BCM event declarations are merged (already met per `bcm-pack` corpus). The first stub iteration (`TASK-001`, covering `RVT.CURRENT_SCORE_RECOMPUTED`) has been delivered and merged.

**Exit condition (DoD)**:
- The five JSON Schemas (Draft 2020-12) — 2 CMDs + 3 RVTs — are present under `process/BNK.RLVR.CAP.BSP.001.SCO/schemas/` (already met in v0.2.0; *authored by `/process`*, this epic only references them).
- A stub (`sources/BNK.RLVR.CAP.BSP.001.SCO/stub/`) publishes simulated payloads conforming to all three RVT schemas onto exchange `bsp.001.sco-events` with the routing keys declared in `process/BNK.RLVR.CAP.BSP.001.SCO/bus.yaml`.
- Every published message carries the UUIDv7 envelope (`message_id`, `correlation_id` = `case_id`, `causation_id`, `schema_version`) per `ADR-TECH-STRAT-007` Rule 4 and `bus.yaml.publication.envelope`.
- Stub is activatable / deactivatable via environment configuration (inactive in production).
- A consumer probe (the existing `BNK.RLVR.CAP.CHN.001.DSH` or a temporary test consumer) validates that messages flow end-to-end on a local branch worktree.

**Complexity**: S

**Unlocks events**: `BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED` (both RVT pairings), `BNK.RLVR.EVT.BSP.001.SCORE_THRESHOLD_REACHED`.

**Dependencies**: none — founding epic.

---

### Epic 2 — Continuous recomputation (Flow B)
**Goal**: Deliver the real algorithmic core of the capability — accept `CMD.RECOMPUTE_SCORE`, apply the homogeneous trigger model (four upstream trigger kinds), atomically emit `RVT.CURRENT_SCORE_RECOMPUTED` and, when a threshold is crossed, the paired `RVT.SCORE_THRESHOLD_REACHED`.

**Entry condition**:
- Epic 1 delivered (contract frozen, downstream consumers integrated against stub).
- Upstream emitters available either for real or via their own contract stubs: `CAP.BSP.004.AUT` (`TRANSACTION_AUTHORIZED`, `TRANSACTION_REFUSED`) and `BNK.RLVR.CAP.BSP.001.SIG` (`RELAPSE_SIGNAL_QUALIFIED`, `PROGRESSION_SIGNAL_QUALIFIED`).
- Tier thresholds queryable from `BNK.RLVR.CAP.BSP.001.TIE` (read-through configuration of the aggregate).

**Exit condition (DoD)**:
- `AGG.SCORE_OF_BENEFICIARY` accepts `CMD.RECOMPUTE_SCORE`, enforces invariants `INV.SCO.002` (entry-score precondition), `INV.SCO.003` (atomic threshold), `INV.SCO.004` (idempotency by `trigger.event_id`).
- `POL.ON_BEHAVIOURAL_TRIGGER` is bound to four queues (one per upstream binding pattern declared in `bus.yaml`), maps each upstream RVT to a homogeneous `CMD.RECOMPUTE_SCORE`, and applies the error-handling policy (ack-and-drop on duplicate, DLQ on aggregate-not-initialised / beneficiary-unknown).
- PostgreSQL transactional outbox is wired so that the aggregate state and the operational-rail bus message commit atomically (`ADR-TECH-TACT-003`).
- Every emitted RVT carries the UUIDv7 envelope (`message_id` fresh per message, `correlation_id` = `case_id`, `causation_id` = upstream `trigger.event_id` for bus-driven flows or request_id for HTTP back-channel calls).
- `POST /cases/{case_id}/score-recomputations` REST endpoint exists for back-channel / test triggers.
- Integration tests cover: positive trigger → recomputation only; negative trigger → recomputation only; trigger crossing threshold → recomputation + threshold; duplicate trigger → ack-and-drop.

**Complexity**: L

**Unlocks events**: real `RVT.CURRENT_SCORE_RECOMPUTED` and `RVT.SCORE_THRESHOLD_REACHED` payloads (replacing stubbed values).

**Dependencies**:
- `CAP.BSP.004.AUT` (events `TRANSACTION_AUTHORIZED`, `TRANSACTION_REFUSED`) — required upstream.
- `BNK.RLVR.CAP.BSP.001.SIG` (events `RELAPSE_SIGNAL_QUALIFIED`, `PROGRESSION_SIGNAL_QUALIFIED`) — required upstream.
- `BNK.RLVR.CAP.BSP.001.TIE` — tier-thresholds configuration source.

---

### Epic 3 — Entry-score baseline (Flow A)
**Goal**: Materialise the one-shot enrolment baseline — accept `CMD.COMPUTE_ENTRY_SCORE`, enforce `INV.SCO.001` (one-shot), emit `RVT.ENTRY_SCORE_COMPUTED`, and persist `entry_score` as the reference point against which Flow B measures progression.

**Entry condition**:
- Epic 1 delivered.
- Open question on the enrolment trigger resolved: which upstream business event activates `POL.ON_ENROLMENT_COMPLETED`? Best candidate is `EVT.BSP.002.ENROLMENT_COMPLETED` from `CAP.BSP.002.ENR` (`FUNC-0006`), but `ADR-BCM-FUNC-0005` registers no business subscription. **Blocked until `CAP.BSP.002.ENR` is process-modelled and the subscription is added to the BCM.**
- `BNK.RLVR.CAP.SUP.002.BEN` lookup is available for `PRE.002` (`BENEFICIARY_UNKNOWN`) — beneficiary anchor lives in SUPPORT since the `ADR-BCM-FUNC-0016` re-zone (2026-05-15).

**Exit condition (DoD)**:
- `AGG.SCORE_OF_BENEFICIARY` accepts `CMD.COMPUTE_ENTRY_SCORE`, rejects with `ENTRY_SCORE_ALREADY_EXISTS` on retry (`INV.SCO.001`).
- `POL.ON_ENROLMENT_COMPLETED` is bound to the canonical enrolment subscription (no longer `status: placeholder`).
- `POST /cases/{case_id}/entry-score` returns 201 on first call, 409 on subsequent calls.
- `case_id` is validated as UUIDv7 at the API boundary (per `ADR-TECH-STRAT-007` Rule 1) and the emitted `RVT.ENTRY_SCORE_COMPUTED` carries the UUIDv7 envelope.
- Integration tests cover: nominal baseline, duplicate enrolment notification (ack-and-drop), unknown beneficiary (DLQ via `BNK.RLVR.CAP.SUP.002.BEN` lookup miss).

**Complexity**: M

**Unlocks events**: `RVT.ENTRY_SCORE_COMPUTED` (real payload).

**Dependencies**:
- `CAP.BSP.002.ENR` — process model + emitted enrolment event + business subscription registered in BCM (**hard blocker**).
- `BNK.RLVR.CAP.SUP.002.BEN` — beneficiary anchor lookup (SUPPORT capability; relocated from `CAP.REF.001.BEN` per `ADR-BCM-FUNC-0016`).

---

### Epic 4 — Query surface & read-models
**Goal**: Serve the two read endpoints declared in `api.yaml` — `GET /cases/{case_id}/score` (current view) and `GET /cases/{case_id}/score-history` — backed by event-sourced projections, so dashboards, prescriber views, and arbitration can consume scoring state without subscribing to the bus.

**Entry condition**: Epics 2 and 3 delivering real RVT payloads (or Epic 1 stub still active, in which case the projections initially fold stub events — acceptable for early CHN integration).

**Exit condition (DoD)**:
- `PRJ.CURRENT_SCORE_VIEW` projection consumes `RVT.ENTRY_SCORE_COMPUTED` + `RVT.CURRENT_SCORE_RECOMPUTED`, backs `BNK.RLVR.RES.BSP.001.CURRENT_SCORE`.
- `PRJ.SCORE_HISTORY` projection feeds chronological history (24-month retention per the model).
- `QRY.GET_CURRENT_SCORE` returns the projection with ETag + 5-second `max-age` cache contract.
- `QRY.LIST_SCORE_HISTORY` accepts `since` + `limit` filters (default 50, max 500).
- Both endpoints traced via OpenTelemetry per `ADR-TECH-STRAT-005`.
- Smoke-tested against three known consumers: `BNK.RLVR.CAP.CHN.001.DSH` (progression bar), `CAP.CHN.002.VUE` (prescriber timeline), `BNK.RLVR.CAP.BSP.001.ARB` (algorithmic vs override check).

**Complexity**: M

**Unlocks events**: none (read-side).

**Dependencies**: Epic 2 strongly; Epic 3 to back the `entry_score` field of the current view with a real value.

---

### Epic 5 — Model versioning & operability hardening
**Goal**: Productionise the scoring service — explicit `model_version` governance, snapshotting tuning, OpenTelemetry dashboards, DLQ runbooks, contract harness for the public API and bus surface.

**Entry condition**: Epics 1–4 delivered. A first real `model_version` is in service.

**Exit condition (DoD)**:
- Active scoring `model_version` is config-driven, gated by `ADR-BCM-GOV-0002` (BCM arbitration board) before any production deployment.
- Snapshotting strategy validated (default `every-100-events` from `aggregates.yaml` is appropriate, or tuned with rationale).
- OpenTelemetry dashboards expose: recomputation rate per trigger kind, threshold-crossing rate, DLQ depth on each subscription queue, p50/p95 latency on the two queries.
- Contract harness (`/harness-backend BNK.RLVR.CAP.BSP.001.SCO`) produces `openapi.yaml` + `asyncapi.yaml` under `sources/BNK.RLVR.CAP.BSP.001.SCO/backend/contracts/specs/` with full bidirectional `x-lineage` to `process/` and the BCM corpus.
- DLQ runbook covers the two flagged error codes (`AGGREGATE_NOT_INITIALISED`, `BENEFICIARY_UNKNOWN`).

**Complexity**: M

**Unlocks events**: none.

**Dependencies**: Epic 4 (the harness derives `openapi.yaml` from `api.yaml`).

---

## Dependency Map

| Epic | Depends On | Type |
|------|-----------|------|
| Epic 1 | — | Founding |
| Epic 2 | Epic 1 | Sequential — same capability |
| Epic 2 | CAP.BSP.004.AUT (TRANSACTION_AUTHORIZED, TRANSACTION_REFUSED) | Cross-capability (upstream) |
| Epic 2 | BNK.RLVR.CAP.BSP.001.SIG (RELAPSE/PROGRESSION qualified signals) | Cross-capability (upstream) |
| Epic 2 | BNK.RLVR.CAP.BSP.001.TIE (tier-thresholds config) | Cross-capability (configuration source) |
| Epic 3 | Epic 1 | Sequential — same capability |
| Epic 3 | CAP.BSP.002.ENR (ENROLMENT_COMPLETED + subscription registered in BCM) | Cross-capability — **hard blocker** |
| Epic 3 | BNK.RLVR.CAP.SUP.002.BEN (beneficiary anchor lookup) | Cross-capability (SUPPORT — post-rezone per ADR-BCM-FUNC-0016) |
| Epic 4 | Epic 2 | Sequential |
| Epic 4 | Epic 3 (for `entry_score` field) | Sequential — soft (can integrate progressively) |
| Epic 5 | Epic 4 | Sequential |

---

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| The enrolment trigger for Flow A (Epic 3) is never confirmed because `CAP.BSP.002.ENR` is not yet process-modelled. | M | H | Park Epic 3 as a tracked dependency. Move forward with Epics 2 + 4 against the stubbed entry-score value. Force a sync with the BCM governance board (`ADR-BCM-GOV-0002`) before Epic 3 starts. |
| Atomic threshold detection (`INV.SCO.003`) becomes unsustainable as the aggregate's throughput rises — the chosen domain-event-DDD form bundles 1 or 2 RVTs per command, which downstream consumers must always treat as a single unit. | M | M | Document the invariant explicitly in `aggregates.yaml` (already done). If pressure rises, lift the threshold detection to a separate observer reacting to `RVT.CURRENT_SCORE_RECOMPUTED` (already flagged as an open question) — requires a deprecation cycle on the bundled emission. |
| Upstream BSP.004.AUT or BSP.001.SIG slip → Flow B cannot be end-to-end tested. | M | H | Build Epic 2 against the upstream capabilities' own development stubs (each is contract-first per the same `ADR-BCM-URBA-0009` pattern); insist on contract stubs being merged before Epic 2 starts. |
| Scoring model version is changed in production without governance review. | L | H | Enforce config-driven `model_version` activation gated by the BCM arbitration board (`ADR-BCM-GOV-0002`) — operationalised in Epic 5. |
| Stub schemas drift from the real algorithm's emitted payloads. | L | M | The five JSON Schemas in `process/.../schemas/` are the single source of truth (all present since v0.2.0). Both stub and real handler are validated against them in CI. Contract harness in Epic 5 closes the loop bidirectionally. |
| `case_id` ↔ `internal_id` resolution leaks into the producer side, in violation of `ADR-TECH-STRAT-004` + `ADR-TECH-STRAT-007`. | L | M | `bus.yaml` explicitly forbids it (`identity_resolution: producer NEVER carries internal_id`; resolution delegated to `BNK.RLVR.CAP.SUP.002.BEN`). Enforced by code review and contract validation. |
| Consumers still bind to the legacy `CAP.REF.001.BEN` lookup after the `ADR-BCM-FUNC-0016` re-zone, breaking identity resolution for Epic 3. | L | M | Document the relocation in this roadmap's strategic alignment + Epic 3 dependency. Cross-check during `/code` / `/fix` cycles that any beneficiary lookup uses `BNK.RLVR.CAP.SUP.002.BEN`. |

---

## Recommended Sequencing

- **Critical path**: Epic 1 → Epic 2 → Epic 4 → Epic 5. Flow B carries the differentiating core-domain value of the capability; the query surface and the operability hardening close the loop.
- **Epic 3 — deferred, not parallelisable.** Epic 3 (entry-score baseline) is structurally independent of Epic 2 once Epic 1 is done, but it has a **hard blocker**: `CAP.BSP.002.ENR` has no process model yet, no enrolment business subscription is registered in `ADR-BCM-FUNC-0005`, and `POL.ON_ENROLMENT_COMPLETED` is `status: placeholder` in the process model. Until the BCM governance board produces that subscription, Epic 3 cannot enter — describing it as "parallelisable with Epic 2" would understate the blocker. The "Risks" section keeps it as a tracked dependency to flag at every BCM review cycle. When the blocker clears, Epic 3 can rejoin the wave alongside Epic 4.
- **Suggested ordering on the kanban**:
  1. Finish Epic 1 (extend stub coverage to the two remaining RVTs — currently `TASK-001` covered `CURRENT_SCORE_RECOMPUTED` only).
  2. Start Epic 2 once upstream BSP.004.AUT and BSP.001.SIG stubs are merged.
  3. Epic 4 begins as soon as Epic 2 produces real `CURRENT_SCORE_RECOMPUTED` payloads. Do not gate Epic 4 on Epic 3 — the query surface can read the projection with a null `entry_score` until Flow A unblocks.
  4. Move Epic 3 from the **deferred** bucket to **ready** only when the enrolment-trigger open question is resolved at the BCM level. At that point Epic 3 can run in parallel with Epic 4.
  5. Epic 5 closes the loop with operability and contract harness.

---

## Open Questions

- **Enrolment trigger for Flow A** — Which upstream business event activates `POL.ON_ENROLMENT_COMPLETED`? Best candidate is `EVT.BSP.002.ENROLMENT_COMPLETED` from `CAP.BSP.002.ENR` (`FUNC-0006`), but no business subscription is registered in `ADR-BCM-FUNC-0005`. Must be resolved at the BCM governance board before Epic 3 starts.
- **Threshold detection location** — atomic in the aggregate (current choice, `INV.SCO.003`) vs. separate observer reacting to `RVT.CURRENT_SCORE_RECOMPUTED`. Trade-off: atomicity vs. operational decoupling. Revisit at Epic 5 if throughput pressure justifies it.
- **Aggregate granularity** — one aggregate per `case_id` (current choice) vs. one per `(case_id, model_version)`. Revisit if model versioning becomes a first-class invariant.
- **Tier-thresholds read-through caching** — `aggregates.yaml` declares `tier_thresholds` as `read-through` from `BNK.RLVR.CAP.BSP.001.TIE`. Cache invalidation policy when `BNK.RLVR.CAP.BSP.001.TIE` updates its configuration must be specified at Epic 2 time.
- **Score recomputation throughput targets** — no NFRs surfaced in `ADR-BCM-FUNC-0005`. Must be elicited before Epic 5 to dimension snapshotting and queue capacity.

---

## Knowledge Source
- bcm-pack ref: `main`
- Capability pack mode: `deep`
- Pack date: 2026-05-15
- Process model version: `process/BNK.RLVR.CAP.BSP.001.SCO/` **v0.2.0** (merged on `main`) — re-pointed at the post-rezone `BNK.RLVR.CAP.SUP.002.BEN`, added UUIDv7 envelope per `ADR-TECH-STRAT-007`, added `ADR-TECH-STRAT-008` multi-faceted-producer framing, ratified tactical stack `ADR-TECH-TACT-003` (Python / FastAPI / PostgreSQL / RabbitMQ / Kafka), wrote the 4 previously missing JSON Schemas (now 5 total under `schemas/`).
- Existing tasks: `TASK-001` (status: `done`, PR #2 + remediation PR #5) — first iteration of Epic 1 (stub for `RVT.CURRENT_SCORE_RECOMPUTED`).
