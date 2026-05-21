# Process Model — BNK.RLVR.CAP.SUP.002.BEN (Beneficiary Identity Anchor)

> **Layer**: Process Modelling (DDD tactical) — sits between Big-Picture Event
> Storming (banking-knowledge: BCM, FUNC ADR, URBA / TECH-STRAT / TECH-TACT
> ADRs) and Software Design (this repo's `roadmap/`, `tasks/`, `sources/`).
> **Source of truth for**: commands accepted, aggregate boundaries, reactive
> policies, read-model surface, bus topology, wire schemas of this capability.
> **NOT a roadmap, plan, or implementation**: this folder is durable across
> re-roadmaps and re-implementations of the same FUNC ADR. The
> `roadmap/BNK.RLVR.CAP.SUP.002.BEN/` folder consumes it.

## Delta v0.2.0 (2026-05-16)

Add `actor` to the RVT envelope and tighten `PRJ.ANCHOR_HISTORY.fed_by`
with explicit per-field sourcing.

| File | Change |
|---|---|
| `schemas/BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json` | Added required `envelope.actor` field with shape `{kind: human \| service \| system, subject: string, on_behalf_of?: string}`. New `Actor` $def. |
| `bus.yaml` | Bumped to v0.2.0. Added `ADR-TECH-STRAT-003` to `governing_adrs`. New `publication.envelope` block documenting the agreed shape, including the new `actor` field. |
| `read-models.yaml` | Bumped to v0.2.0. Added `ADR-TECH-STRAT-003` to `governing_adrs`. Restructured `PRJ.ANCHOR_HISTORY.fed_by` from a flat RVT list to an `[{rvt, sources}]` form that maps each projection column to its precise wire-format source (`payload.*` or `envelope.actor`). Sharpened `update_strategy` text to flag that `actor.subject` is itself audit-grade personal data with the same 7-year retention. The `actor` projection column keeps its name — implementation chooses JSONB vs decomposed storage. |

No stable identifier was renamed (`AGG.IDENTITY_ANCHOR`, the 5 commands,
`POL.ON_RIGHT_EXERCISED` placeholder, `PRJ.ANCHOR_DIRECTORY` /
`ANCHOR_HISTORY`, `QRY.GET_ANCHOR` / `GET_ANCHOR_HISTORY` are all
preserved). The only wire-format change is the new required envelope
field, which is safe to add today because no live producer or consumer
exists for `BNK.RLVR.CAP.SUP.002.BEN` yet (only the stub bundle under
`sources/BNK.RLVR.CAP.SUP.002.BEN/stub/` from TASK-001 — see follow-up note below).

**Follow-up needed (out of scope for this PR)**: the stub for
TASK-001 (`sources/BNK.RLVR.CAP.SUP.002.BEN/stub/`) currently emits payloads
that do not carry `envelope.actor`. A small `/fix` against the open
TASK-001 (or a `/code` re-run with the new schema baseline) is required
to bring the stub into conformance. Suggested stub default:
`{kind: "system", subject: "system:stub-publisher"}`.

## Migration note (2026-05-15)

This capability was previously modelled at `process/BNK.RLVR.CAP.REF.001.BEN/`
(Beneficiary Referential, REFERENTIAL zone). On 2026-05-15,
`ADR-BCM-FUNC-0016` superseded `ADR-BCM-FUNC-0013` and **moved the
capability** to `BNK.RLVR.CAP.SUP.002.BEN` (SUPPORT zone), renaming it to
"Beneficiary Identity Anchor" and re-scoping it to the IS-wide identity-anchor
+ GDPR Art. 17 erasure mechanics. This PR deletes the obsolete
`process/BNK.RLVR.CAP.REF.001.BEN/` folder. Downstream artefacts (`roadmap/BNK.RLVR.CAP.REF.001.BEN/`
and `tasks/BNK.RLVR.CAP.REF.001.BEN/` — 5 tasks) become orphaned and must be
regenerated post-merge via `/roadmap BNK.RLVR.CAP.SUP.002.BEN` then `/task`.

The model is also a **first** in this repo: per `ADR-TECH-TACT-002` the
implementation stack is **Python + FastAPI + PostgreSQL** (with `pgcrypto` +
HashiCorp Vault transit for crypto-shredding), not the .NET 10 default of
`ADR-TECH-STRAT-002`. Downstream `/code` will dispatch to
`implement-capability-python` rather than `implement-capability`.

This capability is the **canonical anchor** for beneficiary identity in the
Reliever IS. Per `ADR-BCM-FUNC-0016`, no other capability may maintain its
own private copy of the anchored PII — every consumer either subscribes to
`BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` to hydrate a local cache (per
`ADR-TECH-STRAT-004`'s dual-referential-access rule) or calls
`QRY.SUP.002.BEN.GET_ANCHOR` synchronously. The same capability operates
the GDPR Art. 17 pseudonymisation-at-anchor mechanics: the destruction of
PII happens HERE, with downstream caches reconciling via the bus on receipt
of the `PSEUDONYMISED` transition.

## Upstream knowledge (consumed, not re-stated)

Fetched via `bcm-pack pack BNK.RLVR.CAP.SUP.002.BEN --deep`. Anything in those slices
is canonical and must NOT be duplicated here:

- `capability_self`, `capability_definition` —
  - `func-adr/ADR-BCM-FUNC-0016` — L2 Beneficiary Identity Anchor
    (supersedes `ADR-BCM-FUNC-0013`)
- `emitted_business_events`, `emitted_resource_events` —
  `BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` /
  `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` (single emitted family;
  carries `BNK.RLVR.RES.SUP.002.BENEFICIARY_IDENTITY`)
- `consumed_business_events`, `consumed_resource_events` — **empty** in v1
  (see Open Question #1)
- `carried_objects` — `BNK.RLVR.OBJ.SUP.002.BENEFICIARY_RECORD` (internal_id,
  last_name, first_name, date_of_birth, contact_details, anchor_status,
  creation_date, pseudonymized_at; PII fields tagged "wipeable under
  GDPR Art. 17")
- `carried_concepts` — `CPT.BCM.000.BENEFICIARY` (canonical, core-domain)
- `governing_urba` — `ADR-BCM-URBA-0001`, `0003`, `0009`, `0010`, `0012`
- `governing_tech_strat` — `ADR-TECH-STRAT-001..008` (the full strategic
  tech corridor; **`007` and `008` are new** since the prior model)
- `tactical_stack` — `ADR-TECH-TACT-002` — Python / FastAPI / PostgreSQL /
  pgcrypto / Vault transit / crypto-shredding / UUIDv7 / GDPR-erasure

## What this folder declares (Process Modelling output)

| File | Captures |
|---|---|
| `commands.yaml` | CMD.* — five verbs (`MINT_ANCHOR`, `UPDATE_ANCHOR`, `ARCHIVE_ANCHOR`, `RESTORE_ANCHOR`, `PSEUDONYMISE_ANCHOR`), preconditions, idempotency strategy, the aggregate that handles each |
| `aggregates.yaml` | AGG.SUP.002.BEN.IDENTITY_ANCHOR — single per-beneficiary aggregate keyed on a server-minted UUIDv7 internal_id; sticky-PII rule on UPDATE; full-snapshot semantics on every emitted event; PSEUDONYMISE wipes PII via crypto-shredding (per ADR-TECH-TACT-002) and is irreversible |
| `policies.yaml` | **Empty** — no upstream subscriptions in BCM v1. The placeholder for the future `POL.ON_RIGHT_EXERCISED` is documented inline |
| `read-models.yaml` | PRJ.* — anchor directory + PII-free anchor history; QRY.* — get-by-internal_id + history. v0.2.0: `PRJ.ANCHOR_HISTORY.fed_by` now carries explicit per-field sourcing including `actor: envelope.actor` |
| `api.yaml` | Derived REST surface (commands → POST/PATCH, queries → GET) |
| `bus.yaml` | Exchange `sup.002.ben-events`, single routing key (`BNK.RLVR.EVT.<...>.BNK.RLVR.RVT.<...>` form per ADR-TECH-STRAT-001 Rule 4), no subscriptions, broad consumer list (every L2 needing identity). v0.2.0: explicit `publication.envelope` block including the new `actor` field |
| `schemas/` | JSON Schemas Draft 2020-12 — five `CMD.*` (command payloads) and one `BNK.RLVR.RVT.*` (resource-event payload, full-snapshot semantics with `transition_kind` discriminator, a conditional shape that nulls PII for the PSEUDONYMISED case, and a UUIDv7 envelope with a required `actor` object since v0.2.0) |

## Scenario walkthroughs

The capability has no event-driven flows in v1 — every transition is
initiated by an HTTP API call. Four flows below illustrate the mint /
update / archive paths plus the GDPR Art. 17 pseudonymisation mechanics
that distinguish this model from the prior `BNK.RLVR.CAP.REF.001.BEN` model.

### Flow A — Minting (driven by upstream enrolment)

```
[BNK.RLVR.CAP.BSP.002.ENR — Enrolment]
                              │
                              ▼ HTTP POST /anchors
                              { client_request_id: "0190a0e1-...-7abc-...",
                                last_name, first_name, date_of_birth,
                                contact_details }
                              │
                              ▼ accepted by
        AGG.SUP.002.BEN.IDENTITY_ANCHOR (created — INV.BEN.001/002/008)
                              │
                              │ mints UUIDv7 internal_id (server-side)
                              │ revision = 1, transition_kind = MINTED
                              ▼ emits
        BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED
            { internal_id, revision=1, transition_kind=MINTED,
              ...full snapshot... }
                              │
                              ▼ replicated to consumers' local caches
        BNK.RLVR.CAP.BSP.001.SCO   ─┐
        BNK.RLVR.CAP.BSP.002.ENR   ─┤
        BNK.RLVR.CAP.BSP.004.ENV   ─┼─▶ each updates its own internal_id-keyed cache
        BNK.RLVR.CAP.CHN.001.DSH   ─┤    via last-write-wins on (internal_id, revision)
        BNK.RLVR.CAP.SUP.001.AUD   ─┤
        BNK.RLVR.CAP.SUP.001.RET   ─┤
        BNK.RLVR.CAP.B2B.001.FLW   ─┘
                              │
                              ▼ caller's HTTP response
                              201 Created { internal_id, ... }
```

### Flow B — Identity update + cache reconciliation

```
[Channel admin tool / ops]
                              │
                              ▼ HTTP PATCH /anchors/{internal_id}
                              { command_id, contact_details: { email: "..." } }
                              │
                              ▼ accepted by
        AGG.SUP.002.BEN.IDENTITY_ANCHOR
                              │
                              │ INV.BEN.003 — only contact_details mutates
                              │ revision = N+1, transition_kind = UPDATED
                              ▼ emits
        BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED
            { revision=N+1, transition_kind=UPDATED,
              ...full snapshot... }
                              │
                              ▼
        Downstream consumer (e.g. BNK.RLVR.CAP.CHN.001.DSH) receives the RVT,
        observes revision N+1 > local N, replaces its local snapshot.
                              │
                              ▼ caller's HTTP response
                              200 OK { ...post-transition record... }
```

### Flow C — GDPR Art. 17 pseudonymisation (HTTP path, v1)

```
[BNK.RLVR.CAP.SUP.001.RET — Beneficiary Rights observes a right-to-be-forgotten
 request from the data subject and, in v1, calls REST directly]
                              │
                              ▼ HTTP POST /anchors/{internal_id}/pseudonymise
                              { command_id,
                                right_exercise_id: "0190b6f2-...-7def-...",
                                reason: "GDPR_ART17_REQUEST",
                                comment: "Subject's written request, ref XYZ" }
                              │
                              ▼ accepted by
        AGG.SUP.002.BEN.IDENTITY_ANCHOR (INV.BEN.006)
                              │
                              │ crypto-shreds last_name, first_name,
                              │ date_of_birth, contact_details
                              │ (pgcrypto + Vault transit per ADR-TECH-TACT-002)
                              │ anchor_status: ACTIVE | ARCHIVED → PSEUDONYMISED
                              │ pseudonymized_at = NOW()
                              │ revision = N+1, transition_kind = PSEUDONYMISED
                              ▼ emits
        BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED
            { revision=N+1, transition_kind=PSEUDONYMISED,
              last_name=null, first_name=null,
              date_of_birth=null, contact_details=null,
              anchor_status="PSEUDONYMISED",
              pseudonymized_at=..., right_exercise_id=... }
                              │
                              ▼ replicated to ALL consumers
        Each consumer:
          - retains internal_id (foreign-key integrity)
          - wipes its locally-cached PII for that internal_id
          - PRJ.ANCHOR_HISTORY captures the PSEUDONYMISED transition
            (PII-free row — survives Art. 17)
                              │
                              ▼ caller's HTTP response
                              200 OK { ...PII-nulled record... }
                              │
                              ▼ BNK.RLVR.CAP.SUP.001.RET observes its own RVT
                              and closes the right-exercise loop.
```

### Flow D — Archival on programme exit

```
[Programme administration / future automated exit signal]
                              │
                              ▼ HTTP POST /anchors/{internal_id}/archive
                              { command_id,
                                reason: "PROGRAMME_EXIT_SUCCESS",
                                comment: "Final tier reached" }
                              │
                              ▼ accepted by
        AGG.SUP.002.BEN.IDENTITY_ANCHOR (INV.BEN.004)
                              │
                              │ anchor_status: ACTIVE → ARCHIVED
                              │ revision = N+1, transition_kind = ARCHIVED
                              ▼ emits
        BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED
            { revision=N+1, transition_kind=ARCHIVED,
              anchor_status=ARCHIVED, ...full snapshot... }
                              │
                              ▼ downstream consumers note the archived state
                              and may pause local-cache eviction (records
                              remain queryable for historical resolution).
```

## Open process-level questions (must be resolved before `/code`)

These questions are repeated from the YAMLs (`open_questions` and inline
notes) so reviewers can see the structural gaps in one place.

1. **Pseudonymisation trigger — event-driven path not yet modelled.**
   `ADR-BCM-FUNC-0016` declares the intent to subscribe to
   `RightExercised.Processed` from `BNK.RLVR.CAP.SUP.001.RET` to drive
   `PSEUDONYMISE_ANCHOR` reactively. The BCM corpus does not yet declare
   the consumed business / resource event chain
   (`consumed_business_events` and `consumed_resource_events` are both
   empty for this capability). v1 of the model uses an **HTTP-only**
   trigger: `BNK.RLVR.CAP.SUP.001.RET` (or a DPO admin tool) calls
   `POST /anchors/{internal_id}/pseudonymise` directly. When the BCM grows
   the consumed event family, re-run `/process BNK.RLVR.CAP.SUP.002.BEN` to add
   `POL.SUP.002.BEN.ON_RIGHT_EXERCISED` (the placeholder body is
   documented inline in `policies.yaml`).

2. **`internal_id` is the sole resolution key.** Per
   `ADR-BCM-FUNC-0016`, identity is owned by this capability alone — the
   aggregate accepts no caller-supplied identifier on MINT and the model
   exposes no secondary lookup query:
   - Idempotency on MINT flows through a **caller-supplied UUIDv7
     `client_request_id`** with a 30-day window.
   - There is **no secondary lookup**; downstream consumers resolve a
     beneficiary by `internal_id` only.
   Downstream consumers observe the `MINTED` RVT, key their local cache
   on `internal_id`, and use their own correlation field on the way in.
   Confirm with each consumer (`BNK.RLVR.CAP.BSP.001.SCO`, `BNK.RLVR.CAP.BSP.002.ENR`,
   `BNK.RLVR.CAP.BSP.004.ENV`) that this does not break a necessary lookup; if it
   does, surface it as a new BCM business-event before re-modelling.

3. **Crypto-shredding mechanics are an implementation detail.** The
   `PSEUDONYMISE_ANCHOR` invariant (INV.BEN.006) only constrains the
   observable post-condition: PII fields are not recoverable.
   `ADR-TECH-TACT-002` ratifies the stack (`pgcrypto` + Vault transit
   + per-anchor key with crypto-shredded handle), and the
   `implement-capability-python` agent owns the design choice between
   per-anchor keys vs per-zone keys. The model deliberately does not
   constrain it.

4. **Anchor history retention and Art. 17.** `PRJ.ANCHOR_HISTORY` is
   PII-free by construction and survives `PSEUDONYMISE`. Retention is
   set to **7 years** (GDPR + AML audit floor). If the DPO requires a
   shorter retention or a periodic purge of old `MINTED` / `UPDATED`
   audit rows, this becomes a follow-up FUNC ADR and a `/process` re-run.

5. **Consumer migration after this PR merges.**
   - `process/BNK.RLVR.CAP.REF.001.BEN/` is deleted by this PR.
   - `roadmap/BNK.RLVR.CAP.REF.001.BEN/` and `tasks/BNK.RLVR.CAP.REF.001.BEN/` (5 tasks) are
     orphaned. Run `/roadmap BNK.RLVR.CAP.SUP.002.BEN` then `/task` to regenerate
     them under the new ID.
   - Downstream `process/` folders that name `BNK.RLVR.CAP.REF.001.BEN` as their
     identity resolver (`BNK.RLVR.CAP.BSP.001.SCO`, `BNK.RLVR.CAP.BSP.004.ENV` — see
     `bus.yaml.consumers[].migration_note`) need a delta `/process` pass
     to re-point their `bus.yaml.identity_resolution` and
     `bus.yaml.subscriptions[*].source_capability` at `BNK.RLVR.CAP.SUP.002.BEN`
     and the new exchange `sup.002.ben-events`.

## Governance

| ADR | Role |
|---|---|
| `ADR-BCM-FUNC-0016` | L2 Beneficiary Identity Anchor — defines the golden-record + GDPR Art. 17 pseudonymisation mandate; supersedes `ADR-BCM-FUNC-0013` |
| `ADR-BCM-URBA-0001` / `0003` / `0009` / `0010` / `0012` | TOGAF-Extended IS BCM, one-capability-one-responsibility, event meta-model, L2 as urbanization pivot, canonical concept rule |
| `ADR-TECH-STRAT-001` | Bus rules (exchange-per-L2, routing-key convention `BNK.RLVR.EVT.<...>.BNK.RLVR.RVT.<...>`, design-time schema governance, dual-rail operational vs analytical) — NORMATIVE for `bus.yaml` |
| `ADR-TECH-STRAT-003` | API contract strategy — REST/HTTP, JWT-borne actor; informs `api.yaml` |
| `ADR-TECH-STRAT-004` | Data and Referential Layer — PII governance, dual-referential-access (bus + QRY), retention / right-to-be-forgotten guidance |
| `ADR-TECH-STRAT-007` (NEW) | Identifier Strategy — UUIDv7 federated minting, immutable anchors, no-recycle-forever, idempotency-as-identifier — **normative for the MINT contract and for the envelope's `message_id` / `correlation_id` / `causation_id`** |
| `ADR-TECH-STRAT-008` (NEW) | Information Publication Model — capability as a multi-faceted information producer (operational rail RabbitMQ, analytical rail Kafka, REST QRY) — frames the `bus.yaml` + `api.yaml` + `read-models.yaml` triad |
| `ADR-TECH-TACT-002` (NEW) | Tactical stack ratification: Python / FastAPI / PostgreSQL / pgcrypto / Vault transit / crypto-shredding / UUIDv7 / GDPR-erasure — the implementation downstream consumes this |
