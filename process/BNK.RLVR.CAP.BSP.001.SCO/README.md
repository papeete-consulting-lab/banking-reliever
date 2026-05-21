# Process Model — BNK.RLVR.CAP.BSP.001.SCO (Behavioural Scoring)

> **Layer**: Process Modelling (DDD tactical) — sits between Big-Picture Event
> Storming (banking-knowledge: BCM, FUNC / URBA / TECH-STRAT / TECH-TACT ADRs)
> and Software Design (this repo's `roadmap/`, `tasks/`, `sources/`).
> **Source of truth for**: commands accepted, aggregate boundaries, reactive
> policies, read-model surface, bus topology, wire schemas of this capability.
> **NOT a roadmap, plan, or implementation**: this folder is durable across
> re-roadmaps and re-implementations of the same FUNC ADR. The
> `roadmap/BNK.RLVR.CAP.BSP.001.SCO/` folder consumes it.

## Delta v0.2.0 (2026-05-15)

This refresh re-points the model at the post-rezone universe and incorporates
the new strategic + tactical tech ADRs that have landed since v0.1.0. **No
identifier was renamed**; consumers keyed on AGG / CMD / POL / PRJ / QRY ids
are unaffected.

| Change | Reason |
|---|---|
| `bus.yaml.identity_resolution`: `BNK.RLVR.CAP.REF.001.BEN` → `BNK.RLVR.CAP.SUP.002.BEN`; `BNK.RLVR.OBJ.REF.001.BENEFICIARY_RECORD` → `BNK.RLVR.OBJ.SUP.002.BENEFICIARY_RECORD` | Upstream rezone — `ADR-BCM-FUNC-0016` supersedes `ADR-BCM-FUNC-0013` (REFERENTIAL → SUPPORT) |
| `commands.yaml`: `CMD.COMPUTE_ENTRY_SCORE.preconditions[1]` and `errors.BENEFICIARY_UNKNOWN.when` re-pointed | Same upstream rezone |
| Added `ADR-TECH-STRAT-007` to `aggregates.yaml`, `commands.yaml`, `bus.yaml` meta | UUIDv7 / immutable-anchor / idempotency-as-identifier — frames `case_id`, `trigger.event_id`, the bus envelope (`message_id`, `correlation_id`, `causation_id`) |
| Added `ADR-TECH-STRAT-008` to `bus.yaml`, `read-models.yaml`, `api.yaml` meta | Capability-as-multi-faceted-producer — frames the operational + analytical + REST publication triad |
| Added `ADR-TECH-TACT-003` to every meta block | Per-capability tactical stack ratification: Python + FastAPI + PostgreSQL + RabbitMQ (operational) + Kafka (analytical, downstream of the same outbox via CDC) |
| `bus.yaml.publication.envelope` block (NEW) | Declares the UUIDv7 envelope shape (`message_id` / `correlation_id` / `causation_id`) per `ADR-TECH-STRAT-007` Rule 4 |
| `bus.yaml`: header reframed to "operational rail; analytical rail downstream of outbox via CDC" | Per `ADR-TECH-STRAT-008` dual-rail framing |
| `aggregates.yaml`: `case_id` field gains a description anchoring it to the upstream UUIDv7 + identity-resolution delegation | Same `ADR-TECH-STRAT-007` framing |
| Wrote 4 missing schemas: `CMD.COMPUTE_ENTRY_SCORE`, `BNK.RLVR.RVT.ENTRY_SCORE_COMPUTED`, `BNK.RLVR.RVT.CURRENT_SCORE_RECOMPUTED`, `BNK.RLVR.RVT.SCORE_THRESHOLD_REACHED` | The prior model marked them `# to produce` / `# exists today` — gap is now closed. All carry the UUIDv7 envelope |
| Tightened `CMD.RECOMPUTE_SCORE.case_id` and `trigger.event_id` to UUIDv7 patterns; updated `$id` and re-pointed the `case_id` description | Wire-format alignment with `ADR-TECH-STRAT-007` |

The rest of the model is **unchanged** from v0.1.0.

## Upstream knowledge (consumed, not re-stated)

Fetched via `bcm-pack pack BNK.RLVR.CAP.BSP.001.SCO --deep`. Anything in those slices
is canonical and must NOT be duplicated here:

- `capability_self`, `capability_definition` —
  - `func-adr/ADR-BCM-FUNC-0005` — L2 breakdown of BNK.RLVR.CAP.BSP.001
- `emitted_business_events` — `BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED`, `BNK.RLVR.EVT.BSP.001.SCORE_THRESHOLD_REACHED`
- `emitted_resource_events` — `BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED`, `BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED`, `BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED`
- `consumed_business_events` / `consumed_resource_events` — four upstream subscriptions:
  - `BNK.RLVR.EVT.BSP.004.TRANSACTION_AUTHORIZED` / `BNK.RLVR.RVT.BSP.004.PAYMENT_GRANTED` (BNK.RLVR.CAP.BSP.004.AUT)
  - `BNK.RLVR.EVT.BSP.004.TRANSACTION_REFUSED` / `BNK.RLVR.RVT.BSP.004.PAYMENT_BLOCKED` (BNK.RLVR.CAP.BSP.004.AUT)
  - `BNK.RLVR.EVT.BSP.001.RELAPSE_SIGNAL_DETECTED` / `BNK.RLVR.RVT.BSP.001.RELAPSE_SIGNAL_QUALIFIED` (BNK.RLVR.CAP.BSP.001.SIG)
  - `BNK.RLVR.EVT.BSP.001.PROGRESSION_SIGNAL_DETECTED` / `BNK.RLVR.RVT.BSP.001.PROGRESSION_SIGNAL_QUALIFIED` (BNK.RLVR.CAP.BSP.001.SIG)
- `carried_objects` — `BNK.RLVR.OBJ.BSP.001.EVALUATION` (evaluation_id, case_id, score_value, contributing_factors, computation_timestamp, model_version, evaluation_type)
- `carried_concepts` — `CPT.BCM.000.SCORE`, `CPT.BCM.000.CASE`, `CPT.BCM.000.MODEL`
- `governing_urba` — `ADR-BCM-URBA-0007/8/9` (event meta-model + capability event ownership)
- `governing_tech_strat` — strategic-tech corridor including `ADR-TECH-STRAT-001` (NORMATIVE for `bus.yaml`), `ADR-TECH-STRAT-004` (PII governance), `ADR-TECH-STRAT-007` (NEW — identifier strategy), `ADR-TECH-STRAT-008` (NEW — publication model)
- `tactical_stack` — `ADR-TECH-TACT-003` (NEW) — Python + FastAPI + PostgreSQL + RabbitMQ + Kafka data-product

## What this folder declares (Process Modelling output)

| File | Captures |
|---|---|
| `commands.yaml` | CMD.* — `COMPUTE_ENTRY_SCORE` (one-shot baseline) and `RECOMPUTE_SCORE` (per-trigger), preconditions, idempotency, the aggregate that handles each, the RVTs each emits |
| `aggregates.yaml` | AGG.SCORE_OF_BENEFICIARY — single per-case singleton; INV.SCO.001..004 (one entry score per case, immutable case_id, atomic threshold detection, idempotency); transactional outbox; snapshot every 100 events |
| `policies.yaml` | POL.ON_BEHAVIOURAL_TRIGGER — homogeneous CMD.RECOMPUTE_SCORE issuance from the four upstream RVTs; POL.ON_ENROLMENT_COMPLETED — placeholder pending BCM declaration of the upstream subscription |
| `read-models.yaml` | PRJ.CURRENT_SCORE_VIEW + PRJ.SCORE_HISTORY (24m retention); QRY.GET_CURRENT_SCORE + QRY.LIST_SCORE_HISTORY |
| `api.yaml` | Derived REST surface (commands → POST, queries → GET) |
| `bus.yaml` | Exchange `bsp.001.sco-events`; three routing keys (one per emitted RVT); UUIDv7 envelope; subscriptions to the four upstream RVTs; consumer list (BNK.RLVR.CAP.BSP.001.ARB / TIE; BNK.RLVR.CAP.CHN.001.DSH / 002.VUE) |
| `schemas/` | JSON Schemas Draft 2020-12 — 2 CMD + 3 RVT, all carrying UUIDv7 fields and the bus envelope per `ADR-TECH-STRAT-007` |

## Scenario walkthrough

Two flows — **enrolment baseline** and **continuous recomputation** — drive every
behaviour of this capability.

### Flow A — Beneficiary enrolment baseline

```
[BNK.RLVR.CAP.BSP.002.ENR — to confirm with FUNC-0006]
        emits BNK.RLVR.EVT.BSP.002.ENROLMENT_COMPLETED
                │
                ▼
   POL.BSP.001.SCO.ON_ENROLMENT_COMPLETED
                │
                ▼ issues
   CMD.BSP.001.SCO.COMPUTE_ENTRY_SCORE { case_id, baseline_signals }
                │
                ▼ handled by
   AGG.BSP.001.SCO.SCORE_OF_BENEFICIARY (created)
                │
                ▼ emits
   BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED   (paired BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED)
```

### Flow B — Continuous recomputation

```
[BNK.RLVR.CAP.BSP.004.AUT]               [BNK.RLVR.CAP.BSP.001.SIG]
   TXN_AUTHORIZED                  RELAPSE_SIGNAL_QUALIFIED
   TXN_REFUSED                     PROGRESSION_SIGNAL_QUALIFIED
                                │
                                ▼
            POL.BSP.001.SCO.ON_BEHAVIOURAL_TRIGGER
                                │
                                ▼ issues
            CMD.BSP.001.SCO.RECOMPUTE_SCORE
                                │
                                ▼ handled by
            AGG.BSP.001.SCO.SCORE_OF_BENEFICIARY
                                │
                                ▼ emits (always)
            BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED
                                │
                                ▼ also emits (conditional — threshold crossed)
            BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED
                                │
                                ▼ consumed by
            BNK.RLVR.CAP.BSP.001.TIE  (tier transition evaluation)
```

## Open process-level questions (must be resolved before `/code`)

- **Trigger of entry score** — FUNC-0005 lists no business subscription for enrolment
  in BNK.RLVR.CAP.BSP.001.SCO's consumed events. Which event activates `COMPUTE_ENTRY_SCORE`?
  Most likely a future `BNK.RLVR.EVT.BSP.002.ENROLMENT_COMPLETED` from BNK.RLVR.CAP.BSP.002.ENR. Until
  resolved, `POL.BSP.001.SCO.ON_ENROLMENT_COMPLETED` is a placeholder. (Unchanged
  since v0.1.0.)
- **Threshold detection** — is "threshold reached" computed inside the score aggregate
  during the same transaction as the recomputation, or by a separate observer reacting
  to `BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED`? The ADR is silent. This sketch picks the
  former (atomic; one transition emits 1 or 2 resource events) — see `INV.SCO.003`.
  (Unchanged since v0.1.0.)
- **Aggregate granularity** — one aggregate per `case_id` (chosen here) vs. one per
  `(case_id, model_version)`. This sketch picks the former; revisit if model versioning
  becomes a first-class invariant. (Unchanged since v0.1.0.)
- **`case_id` provenance** — assumed in this delta to be a UUIDv7 minted by the
  participation-case capability (likely `BNK.RLVR.CAP.BSP.002.ENR`) per `ADR-TECH-STRAT-007`.
  Confirm when `BNK.RLVR.CAP.BSP.002.ENR` is process-modelled — until then the schema accepts
  any UUIDv7 without further provenance constraints.
- **Analytical-rail topology** — `ADR-TECH-STRAT-008` mandates a Kafka data-product
  facet downstream of the operational rail (per the dual-rail framing of
  `ADR-TECH-STRAT-001`). This delta declares that the Kafka topology lives downstream
  of the same PostgreSQL transactional outbox via CDC and is **not** modelled here.
  If the analytical rail needs a different schema (different envelope, different
  topic naming, partition key choices), it becomes its own modelling concern.

## Governance

| ADR | Role |
|---|---|
| `ADR-BCM-FUNC-0005` | L2 breakdown of BNK.RLVR.CAP.BSP.001 — defines emitted/consumed events |
| `ADR-BCM-FUNC-0016` | Identity-anchor relocation — re-points `bus.yaml.identity_resolution` and the precondition of `CMD.COMPUTE_ENTRY_SCORE` |
| `ADR-BCM-URBA-0007/8/9` | Event meta-model + capability event ownership |
| `ADR-TECH-STRAT-001` | Bus rules — NORMATIVE for `bus.yaml` (exchange-per-L2, routing-key convention `BNK.RLVR.EVT.<...>.BNK.RLVR.RVT.<...>`, design-time schema governance, dual-rail operational vs analytical) |
| `ADR-TECH-STRAT-003` | API contract strategy — REST/HTTP, JWT-borne actor; informs `api.yaml` |
| `ADR-TECH-STRAT-004` | Data and Referential Layer — PII governance, dual-referential-access (bus + QRY); the score-flow does not embed PII |
| `ADR-TECH-STRAT-007` (NEW since v0.1.0) | Identifier Strategy — UUIDv7 federated minting; framed `case_id`, `trigger.event_id`, the bus envelope (`message_id` / `correlation_id` / `causation_id`) |
| `ADR-TECH-STRAT-008` (NEW since v0.1.0) | Information Publication Model — capability as multi-faceted producer (operational + analytical + REST) |
| `ADR-TECH-TACT-003` (NEW since v0.1.0) | Tactical stack ratification: Python / FastAPI / PostgreSQL / RabbitMQ / Kafka — informs the implementation downstream (dispatched to `implement-capability-python`) |
