# Roadmap — Beneficiary Identity Anchor (BNK.RLVR.CAP.SUP.002.BEN)

## Capability Summary

> Hold the canonical beneficiary identity record for the entire Reliever IS,
> mint its UUIDv7 with a no-recycle-forever guarantee, and operate the GDPR
> Art. 17 pseudonymisation-at-anchor mechanics.

The capability is the **single source of truth** for beneficiary identity in
the IS — every other capability either subscribes to
`BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` to hydrate a local cache or calls
`QRY.GET_ANCHOR` synchronously. Joint custody: IT Security / Identity & DPO.

Owned business object: `BNK.RLVR.OBJ.SUP.002.BENEFICIARY_RECORD` (UUIDv7
`internal_id`, four PII fields wipeable under Art. 17, anchor lifecycle status
ACTIVE → ARCHIVED → PSEUDONYMISED). Owned canonical concept:
`CPT.BCM.000.BENEFICIARY` (carried, not authored — authored upstream).

## Strategic Alignment

- **Service offer**: identity & GDPR-grade erasure substrate for the whole
  Reliever programme; non-differentiating but non-trivial (`x=0.3, y=0.6`
  on the supporting-domain map per `ADR-BCM-FUNC-0016`).
- **Strategic L1**: `CAP.SUP.002` (Beneficiary Identity Anchor — sole L2
  beneath it).
- **BCM Zone**: `SUPPORT` (relocated from `REFERENTIAL` on 2026-05-15 — the
  identifier-anchor and erasure responsibilities are transverse IT functions
  rather than pivot master data).
- **Governing FUNC ADR**: `ADR-BCM-FUNC-0016` (supersedes
  `ADR-BCM-FUNC-0013`).
- **Strategic-tech anchors**:
  - `ADR-TECH-STRAT-001` — operational rail (RabbitMQ topic exchange,
    outbox, at-least-once)
  - `ADR-TECH-STRAT-003` — REST/HTTP API contract, JWT-borne actor
  - `ADR-TECH-STRAT-004` — PII governance, dual-referential-access
  - `ADR-TECH-STRAT-007` (NEW) — UUIDv7, immutable anchors,
    no-recycle-forever, idempotency-as-identifier
  - `ADR-TECH-STRAT-008` (NEW) — capability as multi-faceted information
    producer (operational + analytical + REST)
- **Tactical stack**: `ADR-TECH-TACT-002` — **Python + FastAPI +
  PostgreSQL + pgcrypto + HashiCorp Vault transit + crypto-shredding**.
  This is the first non-.NET microservice in the programme; `/code` will
  dispatch to `implement-capability-python`.
- **Process Modelling layer** (read-only contract for this roadmap):
  `process/BNK.RLVR.CAP.SUP.002.BEN/` — 1 aggregate (`AGG.IDENTITY_ANCHOR`),
  5 commands, 0 policies (v1), 2 read-models, 2 queries, 1 emitted RVT.
  Mixed file versions: `bus.yaml` and `read-models.yaml` are at **v0.2.0**
  (REST/JWT actor + multi-faceted-producer framing, UUIDv7 envelope on
  every message); `aggregates.yaml`, `commands.yaml`, `policies.yaml`,
  `api.yaml` still at v0.1.0 — semantically aligned, no contract drift,
  next `/process` pass can level them up.

## Implementation Epics

### Epic 1 — Contract & development stub

**Goal**: Publish a runnable stub that emits well-formed
`BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` envelopes on the
`sup.002.ben-events` exchange so downstream consumers (the SCO / ENR / ENV
/ DSH / AUD migrations) can develop against the wire format before the
real microservice exists.
**Entry condition**: `process/BNK.RLVR.CAP.SUP.002.BEN/` merged on `main`
(satisfied as of PR #7).
**Exit condition**:
- A `sources/BNK.RLVR.CAP.SUP.002.BEN/stub/` Python worker is runnable via
  `docker compose up`.
- It connects to a local RabbitMQ, declares the
  `sup.002.ben-events` topic exchange, and publishes one synthetic RVT
  per transition kind (`MINTED`, `UPDATED`, `ARCHIVED`, `RESTORED`,
  `PSEUDONYMISED`) on the canonical routing key.
- Each emitted payload validates against
  `schemas/BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json` (the
  conditional `if/then` for `PSEUDONYMISED` — null PII fields,
  `right_exercise_id` set — is exercised in fixtures).
- The envelope carries UUIDv7 `message_id` / `correlation_id` /
  `causation_id` per `ADR-TECH-STRAT-007` Rule 4.
**Complexity**: S
**Unlocks events**: `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` (stub, all
five `transition_kind`s).
**Dependencies**: none beyond merged process model.
**Task hint**: `task_type: contract-stub` — dispatches to
`implement-capability-python` Mode B.

### Epic 2 — Foundation: anchor minting and synchronous lookup

**Goal**: Deliver the smallest version of the capability that has business
value — an anchor can be minted (UUIDv7 server-generated) and resolved
synchronously by `internal_id`. Every other capability that needs the
canonical identity has a working API to call.
**Entry condition**: Epic 1 done.
**Exit condition**:
- `POST /anchors` accepts `CMD.MINT_ANCHOR`, generates a RFC-9562 UUIDv7,
  persists the row in PostgreSQL, and returns 201 with the new
  `BeneficiaryAnchor` payload.
- Idempotency on `client_request_id` (UUIDv7, 30-day window, `INV.BEN.008`)
  is enforced — a duplicate request returns the original `internal_id` with
  200, NOT 201.
- `GET /anchors/{internal_id}` resolves the anchor from the
  `PRJ.ANCHOR_DIRECTORY` projection, with ETag/304 (60s freshness).
- The MINT transition emits `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with
  `transition_kind: MINTED`, `revision: 1`, full snapshot, via a
  transactional outbox (`ADR-TECH-STRAT-001` Rule 3 — at-least-once).
- 404 on lookup of an unknown `internal_id`; 400 on missing required
  identity fields.
**Complexity**: M
**Unlocks events**: `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with
`transition_kind: MINTED`.
**Dependencies**: Epic 1; PostgreSQL provisioned in the dev environment;
RabbitMQ provisioned.

### Epic 3 — Identity update with sticky-PII semantics

**Goal**: Allow correction of an anchor's PII (typically contact details,
occasionally legal name change) without accidentally erasing fields under
partial integrations. Establishes the sticky-PII invariant that distinguishes
this capability from a naive mass-update endpoint.
**Entry condition**: Epic 2 done.
**Exit condition**:
- `PATCH /anchors/{internal_id}` accepts `CMD.UPDATE_ANCHOR` and applies
  only the fields explicitly present in the payload (`INV.BEN.003`).
- An explicit `null` on a contact channel clears it; an absent field is a
  no-op. Unit / integration tests cover both cases.
- Idempotency on `command_id` (UUIDv7, 30-day window) is enforced — a
  duplicate `command_id` returns the prior post-transition snapshot.
- Rejected with 409 when `anchor_status` is `ARCHIVED` or `PSEUDONYMISED`.
- The transition emits `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with
  `transition_kind: UPDATED`, `revision = N+1`.
- `GET /anchors/{internal_id}` reflects the change (with `revision` bumped)
  within the 60s freshness window — ETag changes immediately, but the
  cached body may be served until `max-age` expires.
**Complexity**: M
**Unlocks events**: `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with
`transition_kind: UPDATED`.
**Dependencies**: Epic 2.

### Epic 4 — Anchor lifecycle (archive / restore)

**Goal**: Provide the operational verbs for programme exit (archive) and
audited reversal (restore). Anchors remain queryable while archived so
historical references resolve, but no further `UPDATE` is accepted until
`RESTORE`.
**Entry condition**: Epic 2 done (can run in parallel with Epic 3).
**Exit condition**:
- `POST /anchors/{internal_id}/archive` accepts `CMD.ARCHIVE_ANCHOR`, flips
  `anchor_status` to `ARCHIVED`, requires a `reason` enum (one of
  `PROGRAMME_EXIT_SUCCESS | PROGRAMME_EXIT_DROPOUT |
  PROGRAMME_EXIT_TRANSFER | ADMINISTRATIVE_ARCHIVAL`).
- `POST /anchors/{internal_id}/restore` accepts `CMD.RESTORE_ANCHOR` and
  flips back to `ACTIVE`. Rejected if not currently `ARCHIVED`.
- Both verbs are idempotent on `command_id` (30-day window).
- Both are rejected with 409 when `anchor_status` is `PSEUDONYMISED`
  (`PSEUDONYMISED` is terminal).
- Both emit `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with the correct
  `transition_kind`.
- `GET /anchors/{internal_id}` continues to resolve archived records
  (referential reads are not gated on status).
**Complexity**: S
**Unlocks events**: `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with
`transition_kind: ARCHIVED | RESTORED`.
**Dependencies**: Epic 2.

### Epic 5 — GDPR Art. 17 pseudonymisation

**Goal**: Operate the right-to-be-forgotten mechanics at the anchor.
Crypto-shred PII while preserving `internal_id` so downstream consumers
keep foreign-key integrity but lose the PII. This is the differentiating
epic of the capability — and the one where `ADR-TECH-TACT-002`
(`pgcrypto` + Vault transit + crypto-shredding) is materialised.
**Entry condition**: Epic 2 done. Epic 3 and Epic 4 ideally done so the
state machine is complete (`ACTIVE` and `ARCHIVED` both transition into
`PSEUDONYMISED`).
**Exit condition**:
- `POST /anchors/{internal_id}/pseudonymise` accepts
  `CMD.PSEUDONYMISE_ANCHOR` and:
  - crypto-shreds `last_name`, `first_name`, `date_of_birth`,
    `contact_details` (the four PII fields tagged in
    `BNK.RLVR.OBJ.SUP.002.BENEFICIARY_RECORD`) so they are not recoverable from
    the database (verifiable: a database-level inspection of the anchor
    row shows null PII or unrecoverable ciphertext);
  - flips `anchor_status` to `PSEUDONYMISED` and sets `pseudonymized_at`
    to NOW();
  - preserves `internal_id` (foreign-key integrity at downstream
    consumers is not broken — `INV.BEN.002`).
- The command requires a `right_exercise_id` (UUIDv7, references the
  upstream right-to-be-forgotten request from `CAP.SUP.001.RET`) and a
  `reason` enum (one of `GDPR_ART17_REQUEST | REGULATORY_ORDER |
  DPO_INITIATED`).
- Operation is **irreversible** — there is no UN-PSEUDONYMISE command, and
  a duplicate `command_id` returns the prior result without re-invoking
  crypto-shredding.
- Emits `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with
  `transition_kind: PSEUDONYMISED`. The payload's PII fields are null;
  the `right_exercise_id` is set; the conditional `if/then` block of
  the RVT schema validates the shape.
- `GET /anchors/{internal_id}` continues to resolve the anchor; PII
  fields come back as `null`; `internal_id` is still resolvable so
  historical references do not break.
- `UPDATE` / `ARCHIVE` / `RESTORE` issued against a `PSEUDONYMISED`
  anchor return 409.
**Complexity**: L
**Unlocks events**: `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with
`transition_kind: PSEUDONYMISED`.
**Dependencies**: Epic 2 (mandatory); Epics 3 and 4 (recommended);
HashiCorp Vault transit engine provisioned in the dev environment;
PostgreSQL `pgcrypto` extension installed.

### Epic 6 — Anchor history projection (audit trail)

**Goal**: Expose a PII-free audit trail of every anchor transition for
audit (`CAP.SUP.001.AUD`) and rights-fulfillment proof
(`CAP.SUP.001.RET`). The projection is by construction PII-free, so it
survives `PSEUDONYMISED` events without re-creating an Art. 17 violation.
**Entry condition**: Epic 5 done (so the projection covers the full set of
`transition_kind` values, including `PSEUDONYMISED`). Can technically
deliver an interim version after Epic 4, but Epic 5's audit story needs
this one.
**Exit condition**:
- The `PRJ.ANCHOR_HISTORY` projection ingests every received
  `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` and writes one row per event
  keyed on `(internal_id, revision)`. Rows carry `transition_kind`,
  `command_id`, `right_exercise_id` (for `PSEUDONYMISED` only), `actor`
  (subject claim from the JWT — `ADR-TECH-STRAT-003`), `occurred_at`.
- **No PII column is materialised** (verifiable: a schema dump of the
  projection table has no name / dob / contact column).
- `GET /anchors/{internal_id}/history` serves the rows in revision order,
  with optional `?since_revision=N` filtering and ETag/304 (max_age=0,
  re-validation on every request).
- Retention policy: 7 years from `occurred_at`; configurable purge job.
- A `PSEUDONYMISED` row remains intact in the history after
  pseudonymisation — the projection is the proof of GDPR-fulfillment.
**Complexity**: M
**Unlocks events**: none (read-side only).
**Dependencies**: Epics 2, 3, 4, 5.

## Dependency Map

| Epic | Depends On | Type |
|------|-----------|------|
| Epic 1 | merged `process/BNK.RLVR.CAP.SUP.002.BEN/` | Stage gate |
| Epic 2 | Epic 1 | Sequential |
| Epic 3 | Epic 2 | Sequential |
| Epic 4 | Epic 2 | Sequential (parallel with Epic 3) |
| Epic 5 | Epic 2 (mandatory); Epics 3 & 4 (recommended); Vault transit; pgcrypto | Sequential |
| Epic 6 | Epics 2, 3, 4, 5 | Sequential |

No cross-capability **inbound** dependency in v1 — the process model has
zero declared subscriptions. The capability is a pure source of truth
driven by HTTP today.

**Cross-capability outbound impact** (consumers that must migrate from
`CAP.REF.001.BEN`'s old exchange to `sup.002.ben-events` once Epic 2
exposes the new feed):

| Consumer | Migration |
|---|---|
| `BNK.RLVR.CAP.BSP.001.SCO` | Re-run `/process BNK.RLVR.CAP.BSP.001.SCO` to re-point `bus.yaml.identity_resolution` and the binding pattern at the new exchange / event family |
| `CAP.BSP.004.ENV` | Same — already names the old capability as identity resolver |
| `CAP.BSP.002.ENR` | Anticipated (most likely caller of `MINT_ANCHOR`); re-process when its model is authored |
| `BNK.RLVR.CAP.CHN.001.DSH`, `CAP.CHN.002.VIE` | Anticipated subscribers; re-process when their models are authored |
| `CAP.B2B.001.FLW` | Anticipated KYC handover consumer |
| `CAP.SUP.001.AUD`, `CAP.SUP.001.RET` | Anticipated `CAP.SUP.001.RET` is also the future emitter of `RightExercised.Processed` (see Open Question #1) |
| `CAP.DAT.*` | Analytical rail (Kafka / data-mesh) ingest |

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Crypto-shredding mechanics are subtle** — getting the pgcrypto + Vault transit interaction right (per-anchor key vs per-zone key, key rotation, recovery semantics) is non-trivial and easy to get wrong in ways that *look* correct but leave PII recoverable | M | H | Make Epic 5 the most heavily tested epic; mandate a database-level inspection in the DoD; involve DPO + IT Security in the test design (joint custody is on the box) |
| **First Python service in the repo** — `implement-capability-python` will be exercised end-to-end for the first time on a non-trivial capability. Tooling gaps (test harness, contract harness, BFF integration) are likely to surface late | M | M | Sequence Epic 1 as a low-stakes shake-down of the Python toolchain; surface tooling gaps to the implementation pipeline before Epic 2 starts |
| **Downstream lookup paths from the prior model have no replacement** — consumers that previously resolved a beneficiary via a secondary lookup key minted upstream now have no equivalent path. The answer for each consumer is either "use your own correlation field on MINT" or "we need a new BCM event" | M | M | Confirm with each downstream consumer (`BNK.RLVR.CAP.BSP.001.SCO`, `CAP.BSP.002.ENR`, `CAP.BSP.004.ENV`) before Epic 2 ships; if any consumer needs an alternate lookup, route it back through reliever-knowledge as a new BCM event before extending this roadmap |
| **`PSEUDONYMISE` is HTTP-only in v1** — `CAP.SUP.001.RET` calls it via REST rather than via a bus subscription. If the call fails or is missed, the right-to-be-forgotten request is not honoured. The BCM does not yet expose the consumed event chain | L | H | Open Question #1 — track until BCM is updated; defensive: require synchronous success from `CAP.SUP.001.RET` before the right is closed; future Epic 7 (event-driven trigger) when BCM grows the chain |
| **Joint-custody governance overhead** — IT Security and DPO co-own the capability. Any DoD checkbox that touches PII or pseudonymisation needs sign-off from both, which can slow the loop | M | L | Surface PII-touching DoD items explicitly in the TASK files; pre-align on the DoD with both owners at the start of Epic 5 |

## Recommended Sequencing

The critical path is **Epic 1 → 2 → 5 → 6**. Epics 3 and 4 are
behaviourally independent of each other and can run in parallel after
Epic 2. They are also independent of Epic 5 in principle, but the
state-machine completeness of Epic 5 (PSEUDONYMISED accepted from both
ACTIVE and ARCHIVED) is easier to test once Epic 4 has shipped.

Suggested wave plan:
- **Wave A**: Epic 1 (single contract-stub task; sets up the Python
  toolchain).
- **Wave B**: Epic 2 (foundation; the longest individual TASK; gates
  everything downstream).
- **Wave C**: Epic 3 ∥ Epic 4 (in parallel — independent state mutations).
- **Wave D**: Epic 5 (PSEUDONYMISE — the differentiating epic; needs
  pgcrypto + Vault transit provisioned).
- **Wave E**: Epic 6 (audit history — read-side only; can technically
  start as soon as Epic 5's RVT semantics are stable in dev).

## Open Questions

- **OQ-1 (FUTURE EPIC)** — **Event-driven pseudonymisation trigger**.
  `ADR-BCM-FUNC-0016` declares the intent to subscribe to
  `RightExercised.Processed` from `CAP.SUP.001.RET`. The BCM corpus does
  not yet declare the consumed event chain. When it does, add an Epic 7
  ("Reactive pseudonymisation policy") that wires
  `POL.SUP.002.BEN.ON_RIGHT_EXERCISED` (the placeholder body is documented
  inline in `process/BNK.RLVR.CAP.SUP.002.BEN/policies.yaml`).
- **OQ-2** — **Crypto-shredding key strategy** (per-anchor vs per-zone vs
  per-IS): deferred to `implement-capability-python` per `ADR-TECH-TACT-002`.
  The model only constrains the observable post-condition (PII not
  recoverable). Surface the chosen strategy as a TECH-TACT delta when Epic
  5 is being implemented.
- **OQ-3** — **`ANCHOR_HISTORY` retention vs Art. 17**. Set to 7y by
  default in the process model (GDPR + AML floor). If the DPO requires
  shorter retention or periodic purge of old `MINTED` / `UPDATED` rows,
  this becomes a follow-up FUNC ADR + a delta `/process` pass.
- **OQ-4** — **Secondary lookup removal from the prior model**. The
  previous model exposed an upstream-key-based idempotency on REGISTER and
  a secondary lookup endpoint. Both are gone in this model — idempotency
  now flows through a caller-supplied UUIDv7 `client_request_id`. Confirm
  with downstream consumers before Epic 2 ships.
- **OQ-5** — *Resolved 2026-05-16*. The orphaned `tasks/CAP.REF.001.BEN/`
  tasks from the prior model were removed; no `roadmap/CAP.REF.001.BEN/`
  ever existed in this checkout. The kanban no longer shows ghost tasks
  against the defunct capability.

## Knowledge Source

- `rlv-knowledge` ref: `main` (default)
- Capability pack mode: `--deep --compact`
- Pack date: 2026-05-16
- Process model ref: `process/BNK.RLVR.CAP.SUP.002.BEN/` on `main` (PR #7 merged)
  — mixed v0.1.0 / v0.2.0 file versions (see Strategic Alignment).
- This roadmap supersedes the implicit roadmap of the prior
  `CAP.REF.001.BEN` model. The 5 orphan tasks under
  `tasks/CAP.REF.001.BEN/` have since been removed; no
  `roadmap/CAP.REF.001.BEN/roadmap.md` ever existed.
- Implementation progress: `TASK-001` (Epic 1, contract-stub) is **done**
  — PR #9 merged in commit `aee0b67` on `2026-05-15`; remediation
  cycle captured under `pr_url` + `fix_pr_urls` in the TASK file.
  `TASK-002..006` exist (mirroring Epics 2-6); `TASK-002` is `needs_info`
  on `OQ.BEN.002` (`external_id` removal cross-consumer check),
  `TASK-003..006` are `blocked` on `TASK-002`.
