# Roadmap — Budget Envelope Management (CAP.BSP.004.ENV)

## Capability Summary
> Allocate categorised budget envelopes for a beneficiary according to their current tier, track their consumption, and emit consumption signals so that downstream capabilities (dashboard, notifications) can update available balances and react to behavioural patterns (consumption, non-consumption).

## Strategic Alignment
- **Service offer**: The envelope is the operational expression of the tier — it is the concrete budget the beneficiary spends against. Its consumption (or non-consumption) is itself a behavioural signal feeding back into the score. Cf. `product-vision/product.md`.
- **L1 strategic capability**: SC.003 — Transaction Control (parent: CAP.BSP.004 — *Contrôle des transactions*)
- **BCM Zone**: BUSINESS_SERVICE_PRODUCTION
- **Governing ADRs**: ADR-BCM-FUNC-0008 (BSP.004 L2 breakdown), ADR-BCM-URBA-0007 (event meta-model), ADR-BCM-URBA-0009 (capability event responsibility)

## Framing Decisions

- **Contract-first delivery**: per `ADR-BCM-URBA-0009`, this capability owns the contract of every event it emits. The first deliverable is the JSON Schemas of `EVT.BSP.004.ENVELOPE_CONSUMED` and `RVT.BSP.004.CONSUMPTION_RECORDED` plus a development stub publishing them. Consumers (`BNK.RLVR.CAP.CHN.001.DSH`, future `BNK.RLVR.CAP.CHN.001.NOT`, scoring feedback loops) develop against these artifacts without waiting for the real envelope engine.
- **Producer-owned stub**: the development stub belongs to this plan. It is decommissioned by this capability when the real envelope engine is ready, transparently for consumers.
- **Scope of Epic 1 = consumption only**: only `EVT.BSP.004.ENVELOPE_CONSUMED` is contracted in Epic 1, because that is what `BNK.RLVR.CAP.CHN.001.DSH` consumes today (per ADR-BCM-FUNC-0009). The other envelope events (`ENVELOPE_ALLOCATED`, `ENVELOPE_UNCONSUMED`) will get their own contract+stub epics when their consumers begin development.
- **Real implementation deferred**: the actual envelope allocation logic, transactional consumption tracking, and persistence are out of scope for the current horizon and will be added when the BSP.004 implementation cycle begins.

---

## Implementation Epics

### Epic 1 — Contract and Development Stub for Envelope Consumption
**Objective**: Produce the JSON Schemas for `EVT.BSP.004.ENVELOPE_CONSUMED` and `RVT.BSP.004.CONSUMPTION_RECORDED`, plus a runnable development stub publishing them, so consumer capabilities can develop in isolation.

**Entry condition**: The two events are declared in the BCM (`bcm/business-event-reliever.yaml`, `bcm/resource-event-reliever.yaml`) — already the case.

**Exit condition (DoD)**:
- JSON Schemas (Draft 2020-12) under `process/CAP.BSP.004.ENV/schemas/`, aligned with the BCM (authored by `/process`)
- A development stub publishes both events with simulated envelope consumption on the agreed subscription point
- The stub is activatable/deactivatable via environment configuration (inactive in production)
- `validate_repo.py` and `validate_events.py` pass

**Complexity**: S

**Unlocked**: development of `BNK.RLVR.CAP.CHN.001.DSH` (and any future consumer of envelope-consumption events) without dependency on the real envelope engine.

**Dependencies**: none.

---

### Epic 2 — Contract and Stub for Allocation and Non-Consumption Events (deferred)
> Out of scope for the current planning horizon. Triggered when the first consumer of `EVT.BSP.004.ENVELOPE_ALLOCATED` or `EVT.BSP.004.ENVELOPE_UNCONSUMED` begins development.

### Epic 3 — Real Envelope Engine (deferred)
> Out of scope for the current planning horizon. Captures the actual allocation rules, transactional consumption tracking, period closure, and orchestration of all ENVELOPE_* events. Will be expanded when the BSP.004 implementation cycle begins.

---

## Dependency Map

| Epic | Depends on | Type |
|------|-----------|------|
| Epic 1 | none | Founding |
| Epic 2 | Epic 1 | Sequential — deferred |
| Epic 3 | Epics 1, 2 | Sequential — deferred |

---

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Stub schema drifts from the eventual real engine — consumers break when the real implementation arrives | M | M | The JSON Schemas are the unique source of truth. The real implementation, when delivered (Epic 3), MUST validate against the same schemas. |

---

## Open Questions

- The L3 sub-decomposition of `CAP.BSP.004` (ENV, ALT, AUT, etc.) — is `CAP.BSP.004.ENV` an L2 or an L3 under `CAP.BSP.004`? Consolidate with the BCM L2/L3 conventions before Epic 3.
- Should `ENVELOPE_UNCONSUMED` be contracted alongside `ENVELOPE_CONSUMED` even if no consumer needs it yet? It is a counter-intuitive but functionally critical signal (relapse detection); deferring it may block scoring-feedback loops later.
