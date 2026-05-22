---
task_id: TASK-001
capability_id: CAP.BSP.004.ENV
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Budget Envelope Management
epic: Epic 1 — Contract and Development Stub for Envelope Consumption
task_type: contract-stub
status: done
priority: high
depends_on: []
loop_count: 0
max_loops: 10
pr_url: https://github.com/Banking-PapeeteConsulting/banking-reliever/pull/6
---

> **Started on:** 2026-05-13

# TASK-001 — Contract and development stub for `EVT.BSP.004.ENVELOPE_CONSUMED`

## Context
`CAP.BSP.004.ENV` allocates and tracks the categorised budget envelopes of a beneficiary. Per `ADR-BCM-URBA-0009`, this capability holds the exclusive responsibility for the contract of the events it emits. As long as the real envelope engine is not implemented, this capability provides a development stub that publishes the contracted events with simulated values, so that consumers (`BNK.RLVR.CAP.CHN.001.DSH` first; future scoring feedback loops, notifications, etc.) can develop in complete isolation.

This task scopes the **consumption** events only (`ENVELOPE_CONSUMED` + `CONSUMPTION_RECORDED`) — the only envelope events `BNK.RLVR.CAP.CHN.001.DSH` consumes today (per ADR-BCM-FUNC-0009). Allocation and non-consumption events will be contracted in their own future epics.

The bus topology — RabbitMQ topic exchange owned by this capability, message format, routing key convention — is normative-fixed by `ADR-TECH-STRAT-001` (*Dual-Rail Event Infrastructure*). Per Rule 2, only the **resource event** gives rise to an autonomous bus message; the business event remains a design-time concept documented for traceability and governance.

## Capability Reference
- Capability: Budget Envelope Management (CAP.BSP.004.ENV)
- Zone: BUSINESS_SERVICE_PRODUCTION
- Governing ADRs: ADR-BCM-FUNC-0008, ADR-BCM-URBA-0007, ADR-BCM-URBA-0009, **ADR-TECH-STRAT-001**

## What needs to be produced

### Contract artifacts (JSON Schema, Draft 2020-12)
Two schemas under `plan/CAP.BSP.004.ENV/contracts/`. Their roles differ:

| File | Role | Event | Carried | BCM source of truth |
|---|---|---|---|---|
| `RVT.BSP.004.CONSUMPTION_RECORDED.schema.json` | **Runtime contract** — every payload published on the bus MUST validate against this schema | Resource event | `OBJ.BSP.004.ALLOCATION` data, framed as *domain event DDD* (transition data) | `bcm/resource-event-reliever.yaml`, `bcm/business-object-reliever.yaml` |
| `EVT.BSP.004.ENVELOPE_CONSUMED.schema.json` | **Design-time documentation** — describes the abstract business fact at the meta-model level; **no autonomous bus message corresponds to it** (cf. ADR-TECH-STRAT-001 Rule 2) | Business event | `OBJ.BSP.004.ALLOCATION` (abstract carrier) | `bcm/business-event-reliever.yaml`, `bcm/business-object-reliever.yaml` |

**Versioning encoding** — each schema declares both:
- A `$id` URL with version segment, e.g. `https://reliever.example.com/contracts/CAP.BSP.004.ENV/RVT.BSP.004.CONSUMPTION_RECORDED/1.0.0/schema.json`.
- A top-level annotation `"x-bcm-version": "1.0.0"` aligned with the BCM event version.

**Correlation key** — `case_id`. Resolution toward `internal_id` via `CAP.REF.001.BEN` is the consumer's concern.

**Payload form** — per `ADR-TECH-STRAT-001` Rule 3, the runtime payload is a *domain event DDD*: transition data of the envelope consumption. Fields: allocation ID, case ID, spending category, `cap_amount`, `consumed_amount` (post-transition), period start/end. **Not** a snapshot of the read model; **not** a field patch. The available balance derivation (`cap_amount - consumed_amount`) is documented in the schema description for consumer convenience but is NOT a transported field.

**Index** — `plan/CAP.BSP.004.ENV/contracts/README.md` lists the two schemas, their roles, BCM IDs, routing key, and known consumers.

### Development stub
A runnable component that publishes the **resource event** on the bus topology agreed by `ADR-TECH-STRAT-001`:

- **Broker** — RabbitMQ (operational rail).
- **Exchange** — a *topic exchange* dedicated to and owned by `CAP.BSP.004.ENV` (Rules 1, 5).
- **Routing key** — `EVT.BSP.004.ENVELOPE_CONSUMED.RVT.BSP.004.CONSUMPTION_RECORDED` (Rule 4).
- **Payload form** — domain event DDD (cf. above; Rule 3).
- **No autonomous EVT message** — per Rule 2.
- **Cadence** — between **1 and 10 events / minute** by default, configurable inside that range. Outside requires explicit override.
- **Realistic envelope consumption** — across multiple categories (e.g. ALIMENTATION, TRANSPORT, …) with `consumed_amount` increasing toward `cap_amount` over time. The category vocabulary is hard-coded illustrative inside the stub (see Resolved Questions); the stub README must explicitly document that the canonical source of category sets per tier is `CAP.REF.001.TIE` and that the future real engine MUST source them there.
- **Configurable simulated case IDs** (`case_id`) — at least one default case, ideally several with distinct envelope category sets.
- **Activatable / deactivatable** via environment configuration (inactive in production).
- **Self-validating** — every payload must validate against the runtime JSON Schema; automated check (CI unit test recommended, site of check at implementer's discretion).

The stub source code lives under `sources/CAP.BSP.004.ENV/stub/` — sibling of the future `sources/CAP.BSP.004.ENV/backend/`.

## Business Events to Produce
This task produces the **contract** of the events listed above and a **stub** publishing the resource event — it does not produce a new business event of its own beyond what BCM already declares.

## Business Objects Involved
- `OBJ.BSP.004.ALLOCATION` — basis of the runtime payload
- `RES.BSP.004.OPEN_ENVELOPE` — read model maintained by consumers
- `OBJ.REF.001.BENEFICIARY_RECORD` (correlation-key resolution; not embedded)

## Required Event Subscriptions
None — this capability is a producer.

## Definition of Done
- [ ] `plan/CAP.BSP.004.ENV/contracts/RVT.BSP.004.CONSUMPTION_RECORDED.schema.json` produced (Draft 2020-12) — **runtime contract**, aligned with the BCM
- [ ] `plan/CAP.BSP.004.ENV/contracts/EVT.BSP.004.ENVELOPE_CONSUMED.schema.json` produced — **design-time documentation only** (no autonomous bus message, per ADR-TECH-STRAT-001 Rule 2)
- [ ] Each schema declares its `$id` with version segment AND a top-level `"x-bcm-version"` annotation matching `1.0.0`
- [ ] Each schema declares `case_id` as the correlation key and documents the resolution path to `internal_id` via `CAP.REF.001.BEN`
- [ ] The runtime schema (RVT) describes a **domain event DDD payload** — transition data of envelope consumption, not a read-model snapshot, not a field patch
- [ ] The available balance derivation (`cap_amount - consumed_amount`) is documented in the runtime schema description (formula in `description`); it is NOT a transported field
- [ ] `plan/CAP.BSP.004.ENV/contracts/README.md` lists the two schemas, their roles, BCM IDs, routing key, and known consumers
- [ ] A runnable development stub publishes `RVT.BSP.004.CONSUMPTION_RECORDED` messages on a RabbitMQ topic exchange owned by `CAP.BSP.004.ENV`, with routing key `EVT.BSP.004.ENVELOPE_CONSUMED.RVT.BSP.004.CONSUMPTION_RECORDED` (no autonomous EVT message)
- [ ] The stub publishes at a configurable cadence in the range **1 to 10 events / minute** by default; outside that range requires explicit override
- [ ] The stub is activatable/deactivatable via environment configuration (inactive in production)
- [ ] Every payload published by the stub validates against the runtime JSON Schema (automated check; CI unit test recommended)
- [ ] The stub source code resides under `sources/CAP.BSP.004.ENV/stub/`
- [ ] The stub README documents the category-vocabulary assumption: illustrative categories are hard-coded inside the stub, and the canonical source per tier is `CAP.REF.001.TIE` (target for the future real engine)
- [ ] `python tools/validate_repo.py` passes without error
- [ ] `python tools/validate_events.py` passes without error

## Acceptance Criteria (business)
A developer working on `BNK.RLVR.CAP.CHN.001.DSH` (or any future consumer of envelope-consumption events) can subscribe a queue to the topic exchange owned by `CAP.BSP.004.ENV`, bind on the routing key, receive payloads validating against the runtime schema, and develop their consumer logic without any direct dependency on the real `CAP.BSP.004.ENV` engine. When the real engine replaces the stub later, no schema-driven consumer code change is required.

## Dependencies
None. This task is self-founding for `CAP.BSP.004.ENV` (Epic 1).

## Resolved Questions

- ✅ **Bus topology** — Resolved via `ADR-TECH-STRAT-001`. RabbitMQ operational rail; topic exchange owned by this capability; only resource events published; routing key `EVT.BSP.004.ENVELOPE_CONSUMED.RVT.BSP.004.CONSUMPTION_RECORDED`; payload format = domain event DDD (Rules 1–6).
- ✅ **Stub source location** — `sources/CAP.BSP.004.ENV/stub/`, sibling of the future `backend/`. Decommissioned when the real engine is delivered.
- ✅ **Category vocabulary** (resolved 2026-05-04) — Hard-coded illustrative categories (e.g. `ALIMENTATION`, `TRANSPORT`, …) inside the stub are acceptable for Epic 1. The canonical source of category sets per tier is `CAP.REF.001.TIE` (per `CPT.BCM.000.PALIER` business rules), but this dependency is deliberately not coupled to the stub: the stub's purpose is to unblock consumer development without waiting on another not-yet-implemented capability. The stub README must document this assumption explicitly so the future real engine knows to source categories from `CAP.REF.001.TIE`.

## Open Questions
_No open questions._
