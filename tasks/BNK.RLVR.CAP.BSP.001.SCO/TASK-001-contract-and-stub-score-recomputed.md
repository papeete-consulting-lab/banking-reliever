---
task_id: TASK-001
capability_id: BNK.RLVR.CAP.BSP.001.SCO
bcm_ref: v1.0.0-1-gb06a4af
capability_name: Behavioural Score
epic: Epic 1 — Contract and Development Stub
task_type: contract-stub
status: done
priority: high
depends_on: []
loop_count: 0
max_loops: 10
pr_url: https://github.com/Banking-PapeeteConsulting/banking-reliever/pull/2
fix_pr_urls:
  - https://github.com/Banking-PapeeteConsulting/banking-reliever/pull/5
---

> **Started on:** 2026-04-28
> **Submitted for review on:** 2026-04-28

# TASK-001 — Contract and development stub for `BNK.RLVR.EVT.BSP.001.SCORE_RECALCULE`

## Context
`BNK.RLVR.CAP.BSP.001.SCO` produces the behavioural score of a beneficiary. Per `ADR-BCM-URBA-0009`, this capability holds the exclusive responsibility for the contract of the events it emits. As long as the real scoring algorithm is not implemented, this capability provides a development stub that publishes the contracted events with simulated values, so that consumers (`BNK.RLVR.CAP.CHN.001.DSH` first; future `BNK.RLVR.CAP.CHN.001.NOT`, scoring feedback loops, etc.) can develop in complete isolation.

The bus topology — RabbitMQ topic exchange owned by this capability, message format, routing key convention — is normative-fixed by `ADR-TECH-STRAT-001` (*Dual-Rail Event Infrastructure*). Per Rule 2 of that ADR, only the **resource event** gives rise to an autonomous bus message; the business event remains a design-time concept documented for traceability and governance, but is not transported.

This task produces:
1. The JSON Schema of the **resource event** emitted by this capability — the runtime contract validated against payloads on the bus.
2. The JSON Schema of the **business event** as design-time documentation (no runtime message corresponds to it).
3. A runnable development stub publishing the resource event on the agreed bus topology.

## Capability Reference
- Capability: Behavioural Score (BNK.RLVR.CAP.BSP.001.SCO)
- Zone: BUSINESS_SERVICE_PRODUCTION
- Governing ADRs: ADR-BCM-FUNC-0005, ADR-BCM-URBA-0007, ADR-BCM-URBA-0009, **ADR-TECH-STRAT-001**

## What needs to be produced

### Contract artifacts (JSON Schema, Draft 2020-12)
Two schemas under `plan/BNK.RLVR.CAP.BSP.001.SCO/contracts/`. Their roles differ:

| File | Role | Event | Carried | BCM source of truth |
|---|---|---|---|---|
| `BNK.RLVR.RVT.BSP.001.SCORE_COURANT_RECALCULE.schema.json` | **Runtime contract** — every payload published on the bus MUST validate against this schema | Resource event | `BNK.RLVR.OBJ.BSP.001.EVALUATION` data, framed as *domain event DDD* (transition data) | `bcm/resource-event-reliever.yaml`, `bcm/business-object-reliever.yaml` |
| `BNK.RLVR.EVT.BSP.001.SCORE_RECALCULE.schema.json` | **Design-time documentation** — describes the abstract business fact at the meta-model level; **no autonomous bus message corresponds to it** (cf. ADR-TECH-STRAT-001 Rule 2) | Business event | `BNK.RLVR.OBJ.BSP.001.EVALUATION` (abstract carrier) | `bcm/business-event-reliever.yaml`, `bcm/business-object-reliever.yaml` |

**Versioning encoding** — each schema declares both:
- A `$id` URL with version segment, e.g. `https://reliever.example.com/contracts/BNK.RLVR.CAP.BSP.001.SCO/BNK.RLVR.RVT.BSP.001.SCORE_COURANT_RECALCULE/1.0.0/schema.json`. A new major/minor/patch version means a new path = explicit deprecation surface.
- A top-level annotation `"x-bcm-version": "1.0.0"` aligned with the BCM event version, so traceability does not require URL parsing.

**Correlation key** — each schema declares `case_id` (case ID) as the correlation key. Beneficiary identity resolution toward `internal_id` of `OBJ.REF.001.BENEFICIARY_RECORD` is performed by consumers via `CAP.REF.001.BEN` lookup (out of scope of this task).

**Payload form** — per `ADR-TECH-STRAT-001` Rule 3, the runtime payload is a *domain event DDD*: the data of an aggregate transition that is coherent and atomic. For `BNK.RLVR.RVT.BSP.001.SCORE_COURANT_RECALCULE` the payload carries: new score value, contributing factors, evaluation type (`INITIAL` / `CURRENT`), computation timestamp, scoring model version, `case_id`. **Not** a complete snapshot of the read model; **not** a technical patch of fields.

**Index** — `plan/BNK.RLVR.CAP.BSP.001.SCO/contracts/README.md` lists the two schemas, their roles (runtime vs documentation), their BCM IDs, the carried object/resource, the routing key convention, and the consumers known today.

### Development stub
A runnable component that publishes the **resource event** on the bus topology agreed by `ADR-TECH-STRAT-001`:

- **Broker** — RabbitMQ (operational rail).
- **Exchange** — a *topic exchange* dedicated to and owned by `BNK.RLVR.CAP.BSP.001.SCO` (Rule 1; only this capability publishes here, Rule 5).
- **Routing key** — `BNK.RLVR.EVT.BSP.001.SCORE_RECALCULE.BNK.RLVR.RVT.BSP.001.SCORE_COURANT_RECALCULE` (Rule 4 — `{BusinessEventName}.{ResourceEventName}`).
- **Payload form** — domain event DDD (cf. above; Rule 3).
- **No autonomous EVT message** — per Rule 2, only the resource event is published on the bus.
- **Cadence** — between **1 and 10 events / minute** by default, configurable inside that range. Outside that range requires explicit override + justification (so neither floods nor starves consumer development).
- **Configurable simulated case IDs** (`case_id`) — at least one default test case, ideally several (`evaluation_type` mix of `INITIAL` and `CURRENT`).
- **Activatable / deactivatable** via environment configuration (inactive in production).
- **Self-validating** — every payload published by the stub must validate against the runtime JSON Schema; this check is automated (recommended: a CI unit test alongside the stub source code, independent of bus availability).

The stub source code lives under `sources/BNK.RLVR.CAP.BSP.001.SCO/stub/` — sibling of the future `sources/BNK.RLVR.CAP.BSP.001.SCO/backend/` (which Epic 2 of the producer's plan will populate when the real scoring algorithm is implemented). The stub directory is decommissioned at that point.

## Business Events to Produce
This task produces the **contract** of the events listed above and a **stub** publishing the resource event — it does not produce a new business event of its own beyond what BCM already declares.

## Business Objects Involved
- `BNK.RLVR.OBJ.BSP.001.EVALUATION` — carried by `BNK.RLVR.EVT.BSP.001.SCORE_RECALCULE`, fields used as the basis of the runtime payload
- `BNK.RLVR.RES.BSP.001.CURRENT_SCORE` — carried by `BNK.RLVR.RVT.BSP.001.SCORE_COURANT_RECALCULE` (resource read model maintained by consumers — not transported as snapshot)
- `OBJ.REF.001.BENEFICIARY_RECORD` (referenced for documentation of the correlation-key resolution path; not embedded)

## Required Event Subscriptions
None — this capability is a producer.

## Definition of Done
- [ ] `plan/BNK.RLVR.CAP.BSP.001.SCO/contracts/BNK.RLVR.RVT.BSP.001.SCORE_COURANT_RECALCULE.schema.json` produced (Draft 2020-12) — **runtime contract**, aligned with `bcm/resource-event-reliever.yaml` and `bcm/business-object-reliever.yaml`
- [ ] `plan/BNK.RLVR.CAP.BSP.001.SCO/contracts/BNK.RLVR.EVT.BSP.001.SCORE_RECALCULE.schema.json` produced — **design-time documentation only** (no autonomous bus message corresponds to it, per ADR-TECH-STRAT-001 Rule 2). The schema is annotated explicitly to mark this role
- [ ] Each schema declares its `$id` with version segment (`/{version}/schema.json`) AND a top-level `"x-bcm-version"` annotation matching the BCM version (`1.0.0`)
- [ ] Each schema declares `case_id` as the correlation key and documents the resolution path to `internal_id` via `CAP.REF.001.BEN`
- [ ] The runtime schema (RVT) describes a **domain event DDD payload** — transition data of the score recalculation, not a read-model snapshot, not a field patch
- [ ] `plan/BNK.RLVR.CAP.BSP.001.SCO/contracts/README.md` lists the two schemas, their roles, BCM IDs, routing key, and known consumers
- [ ] A runnable development stub publishes `BNK.RLVR.RVT.BSP.001.SCORE_COURANT_RECALCULE` messages on a RabbitMQ topic exchange owned by `BNK.RLVR.CAP.BSP.001.SCO`, with routing key `BNK.RLVR.EVT.BSP.001.SCORE_RECALCULE.BNK.RLVR.RVT.BSP.001.SCORE_COURANT_RECALCULE` (no autonomous `EVT.*` message is published, per ADR-TECH-STRAT-001 Rule 2)
- [ ] The stub publishes at a configurable cadence in the range **1 to 10 events / minute** by default; cadence outside that range requires explicit override
- [ ] The stub is activatable/deactivatable via environment configuration (inactive in production)
- [ ] Every payload published by the stub validates against the runtime JSON Schema (automated check; CI unit test recommended — site of the check is at the implementer's discretion)
- [ ] The stub source code resides under `sources/BNK.RLVR.CAP.BSP.001.SCO/stub/`
- [ ] `python tools/validate_repo.py` passes without error
- [ ] `python tools/validate_events.py` passes without error

## Acceptance Criteria (business)
A developer working on `BNK.RLVR.CAP.CHN.001.DSH` (or any future consumer of these events) can subscribe a queue to the topic exchange owned by `BNK.RLVR.CAP.BSP.001.SCO`, bind on the routing key, receive payloads validating against the published runtime schema, and develop their consumer logic without any direct dependency on the real `BNK.RLVR.CAP.BSP.001.SCO` algorithm. When the real algorithm replaces the stub later, no schema-driven consumer code change is required.

## Dependencies
None. This task is self-founding for `BNK.RLVR.CAP.BSP.001.SCO`.

## Resolved Questions

- ✅ **Bus topology** — Resolved via `ADR-TECH-STRAT-001` (*Dual-Rail Event Infrastructure*). RabbitMQ operational rail; topic exchange owned by this capability; only resource events published; routing key `{BusinessEventName}.{ResourceEventName}`; payload format = domain event DDD (Rules 1–6 of the ADR).
- ✅ **Stub source location** — Resolved as `sources/BNK.RLVR.CAP.BSP.001.SCO/stub/`, sibling of the future `backend/` directory that Epic 2 will populate. The stub is decommissioned when the real scoring algorithm is delivered. No project-wide ADR governs this; the convention is local to producer-side stubs and aligned with the existing `sources/{capability-name}/backend/` convention used by `implement-capability`.

## Open Questions
None — all questions resolved during refinement (2026-04-28).
