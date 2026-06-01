# BNK.RLVR.CAP.SUP.002.BEN — Beneficiary Identity Anchor (backend, Mode A)

> **Mode A (full microservice), Python flavour.**
> Scaffolded by `implement-capability(-python)` for **TASK-002 — foundation: MINT + GET**.
> Owns the canonical identity anchor for every beneficiary in Reliever.

This is the real microservice that the TASK-001 stub stands in for. TASK-002
ships **only the MINT + GET path**; UPDATE / ARCHIVE / RESTORE / PSEUDONYMISE
land at TASK-003 … TASK-005.

---

## What it does (TASK-002 scope)

| Verb | Path | What |
|---|---|---|
| `POST` | `/anchors` | `CMD.MINT_ANCHOR` — server-mints a UUIDv7 `internal_id`, persists the anchor row + outbox row in **one transaction**, emits `BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` with `transition_kind: MINTED`. Idempotent on `client_request_id` (30-day window). |
| `GET` | `/anchors/{internal_id}` | `QRY.GET_ANCHOR` — reads `PRJ.ANCHOR_DIRECTORY` (eventually-consistent). Returns the canonical `BeneficiaryAnchor` with `ETag` + `Cache-Control: max-age=60`; 304 on `If-None-Match`; 404 on miss. |
| `GET` | `/health` | Liveness probe. |

The other lifecycle verbs are reserved by the api contract under
`process/BNK.RLVR.CAP.SUP.002.BEN/api.yaml` but are out of scope for TASK-002 — the
service returns the canonical 404 / route-not-found until they ship.

---

## Architecture (Clean Architecture / Hexagonal)

```
src/reliever_beneficiary_anchor/
├── domain/              ← pure Python — AGG.IDENTITY_ANCHOR, VOs, events, errors
├── application/         ← use-case handlers + ports (ABCs)
├── infrastructure/      ← concrete adapters
│   ├── persistence/     ← psycopg 3 async + UoW + projection R/W + migrations
│   ├── messaging/       ← aio-pika publisher + outbox relay + projection consumer
│   ├── schema_validation/ ← jsonschema 4 (Draft 2020-12)
│   └── security/        ← JWT decode (signature verification at the gateway)
├── presentation/        ← FastAPI routers + Pydantic DTOs + lifespan
└── contracts/           ← canonical identifier constants (for harness alignment)
```

Process-layer artefacts (the contract this service implements):

```
process/BNK.RLVR.CAP.SUP.002.BEN/
├── aggregates.yaml        ← AGG.IDENTITY_ANCHOR (INV.BEN.001/002/007/008)
├── commands.yaml          ← CMD.MINT_ANCHOR (PRE.001/002, idempotency, errors)
├── read-models.yaml       ← PRJ.ANCHOR_DIRECTORY, QRY.GET_ANCHOR
├── bus.yaml               ← sup.002.ben-events (topic exchange)
├── api.yaml               ← REST contract (POST /anchors, GET /anchors/{id})
└── schemas/
    ├── CMD.SUP.002.BEN.MINT_ANCHOR.schema.json
    └── BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json
```

> **`process/` is read-only.** This service is a *consumer* of those YAMLs and
> schemas. A repo-wide PreToolUse hook (`process-folder-guard.py`) blocks any
> write under `process/**`. If the contract is wrong, run `/process
> BNK.RLVR.CAP.SUP.002.BEN` to amend the model, never edit a file under `process/` from
> here.

---

## Bus topology

| Property | Value |
|---|---|
| Exchange | `sup.002.ben-events` (topic, durable, owned by `BNK.RLVR.CAP.SUP.002.BEN`) |
| Routing key | `BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` |
| Schema | `process/.../schemas/BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json` |
| Payload form | Domain-event DDD — full post-transition snapshot + revision + `transition_kind` |

Every published envelope carries a fresh UUIDv7 trio (`message_id` /
`correlation_id` / `causation_id`) and the typed `actor` derived from the
JWT `Authorization: Bearer …` header.

---

## Run it

### Prerequisites
- Python 3.12+
- `uv` (recommended) or `pip`
- Docker (for PostgreSQL + RabbitMQ)

### Local — docker-compose (full stack)

```bash
cd sources/BNK.RLVR.CAP.SUP.002.BEN/backend
docker compose up -d --build
```

| Service | Host URL |
|---|---|
| HTTP API | http://localhost:9080 |
| Swagger UI | http://localhost:9080/docs |
| OpenAPI JSON | http://localhost:9080/openapi.json |
| PostgreSQL | postgresql://reliever:reliever@localhost:9043/beneficiary_anchor |
| RabbitMQ AMQP | amqp://admin:password@localhost:9054/ |
| RabbitMQ Mgmt | http://localhost:9055 (admin / password) |

### Local — dev loop (uvicorn + compose for infra only)

```bash
cd sources/BNK.RLVR.CAP.SUP.002.BEN/backend
docker compose up -d postgres rabbitmq
uv sync --extra dev
uv run uvicorn reliever_beneficiary_anchor.presentation.app:app --reload --port 9080
```

### Smoke test

```bash
# Mint an anchor.
curl -i -X POST http://localhost:9080/anchors \
  -H 'Content-Type: application/json' \
  -d '{
    "client_request_id": "018f8e10-aaaa-7000-8000-000000000001",
    "last_name": "Dupont",
    "first_name": "Marie",
    "date_of_birth": "1985-06-21",
    "contact_details": {"email": "marie.dupont@example.org"}
  }'

# Capture the internal_id and GET — wait ~1s for the projection to catch up.
INTERNAL_ID=$(curl -s http://localhost:9080/anchors \
  -H 'Content-Type: application/json' \
  -d '{"client_request_id":"018f8e10-bbbb-7000-8000-000000000001",
       "last_name":"Doe","first_name":"Jane","date_of_birth":"1990-01-15"}' | jq -r .internal_id)
sleep 1
curl -i http://localhost:9080/anchors/$INTERNAL_ID
```

---

## Configuration

Env-var prefix: `RELIEVER_`.

| Env var | Default | Effect |
|---|---|---|
| `RELIEVER_HTTP_HOST` | `0.0.0.0` | Bind host. |
| `RELIEVER_HTTP_PORT` | `8000` (container) / `9080` (host) | Uvicorn port. |
| `RELIEVER_PG_DSN` | `postgresql://reliever:reliever@localhost:9043/beneficiary_anchor` | Postgres DSN (psycopg-compatible). |
| `RELIEVER_PG_MIN_POOL` / `RELIEVER_PG_MAX_POOL` | `1` / `10` | Connection-pool bounds. |
| `RELIEVER_AMQP_URL` | `amqp://admin:password@localhost:9054/` | RabbitMQ URL. |
| `RELIEVER_EXCHANGE_NAME` | `sup.002.ben-events` | Topic exchange owned by this capability. |
| `RELIEVER_PROJECTION_QUEUE` | `sup.002.ben.anchor-directory` | Queue feeding `PRJ.ANCHOR_DIRECTORY`. |
| `RELIEVER_ROUTING_KEY` | `BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED` | Binding key. |
| `RELIEVER_OUTBOX_POLL_INTERVAL_SECONDS` | `0.5` | Relay tick. |
| `RELIEVER_OUTBOX_BATCH_SIZE` | `50` | Max outbox rows drained per tick. |
| `RELIEVER_PROCESS_SCHEMAS_DIR` | vendored package dir (`…/infrastructure/schema_validation/schemas`) | Override only to point at a different JSON-Schema snapshot. The model lives upstream in reliever-knowledge (`rlv-knowledge process`). |
| `RELIEVER_MIGRATIONS_DIR` | `<backend>/migrations` | Migration files. |
| `RELIEVER_RUN_OUTBOX_RELAY` | `true` | Disable in tests where the relay must be quiescent. |
| `RELIEVER_RUN_PROJECTION_CONSUMER` | `true` | Disable for relay-only deployments. |
| `RELIEVER_RUN_MIGRATIONS_ON_STARTUP` | `true` | Apply migrations on lifespan startup. |

---

## Tests

```bash
uv sync --extra dev

# Unit tests — broker-free, no docker required.
uv run pytest tests/unit -q

# Integration tests — require docker compose up (postgres + rabbitmq).
docker compose up -d postgres rabbitmq
uv run pytest tests/integration -q
```

If Postgres or RabbitMQ are unreachable, the integration suite **skips
gracefully** (see `tests/integration/conftest.py`).

---

## DoD verification

| Item | Status |
|---|---|
| Layered package layout | ✅ — see *Architecture* above |
| `docker compose up` starts service + Postgres + Rabbit | ✅ — `docker-compose.yml` |
| Migrations create `anchor`, `anchor_directory`, `outbox`, `idempotency_keys` | ✅ — `migrations/001_init.sql` |
| POST /anchors validates body against canonical schema; rejects caller-supplied `internal_id`; mints UUIDv7; persists row; returns 201 | ✅ — `presentation/routers.py`, `application/handlers.py`, `domain/aggregate.py` |
| Idempotent re-post → 200 with `REQUEST_ALREADY_PROCESSED` | ✅ — `application/handlers.py::MintAnchorHandler.handle` + `idempotency_keys` table |
| Missing identity fields → 400 `IDENTITY_FIELDS_MISSING` | ✅ — `domain/aggregate.py::IdentityAnchor.mint` raises; presentation maps to 400 |
| Outbox row appended in same transaction; relay publishes RVT with correct exchange + routing key + `MINTED` / revision=1 | ✅ — `infrastructure/persistence/unit_of_work.py` + `infrastructure/messaging/outbox_relay.py` |
| Emitted payload validates against canonical RVT schema (pre-publish) | ✅ — handler validates before outbox append |
| Envelope carries UUIDv7 `message_id` / `correlation_id` / `causation_id` + typed `actor` | ✅ — `application/handlers.py::_build_rvt_payload` |
| Projection consumer reads RVT + LWW-upserts `anchor_directory` | ✅ — `infrastructure/messaging/projection_consumer.py` + `infrastructure/persistence/projection.py` |
| GET /anchors/{id} returns BeneficiaryAnchor with ETag + max-age=60; 304 on If-None-Match; 404 on miss | ✅ — `presentation/routers.py::get_anchor` |
| Eventual-consistency contract: integration test exercises post-catchup window | ✅ — `tests/integration/test_mint_get.py::test_get_anchor_after_projection_catches_up_returns_200` |
| No write to `process/BNK.RLVR.CAP.SUP.002.BEN/` | ✅ — every read is via `RELIEVER_PROCESS_SCHEMAS_DIR` (RO mount in compose) |
| TASK-001 stub README updated | ✅ — see `sources/BNK.RLVR.CAP.SUP.002.BEN/stub/README.md` (decommissioning note added) |
| `pytest` unit + integration pass | ⏳ — `pytest tests/unit` runs offline; `pytest tests/integration` requires docker compose |

---

## Lineage

| Layer | Artefact |
|---|---|
| FUNC | `ADR-BCM-FUNC-0016` |
| URBA | `ADR-BCM-URBA-0009`, `ADR-BCM-URBA-0010`, `ADR-BCM-URBA-0012` |
| TECH-STRAT | `ADR-TECH-STRAT-001` (bus + outbox), `003` (REST + JWT), `004` (PII + dual referential), `007` (UUIDv7), `008` (publication model) |
| TECH-TACT | `ADR-TECH-TACT-002` (Python / FastAPI / psycopg / aio-pika / PostgreSQL + pgcrypto / Vault transit) |
| Process | `process/BNK.RLVR.CAP.SUP.002.BEN/{aggregates,commands,read-models,bus,api,policies}.yaml` |
| Schemas | `process/BNK.RLVR.CAP.SUP.002.BEN/schemas/{CMD.MINT_ANCHOR,RVT.BENEFICIARY_ANCHOR_UPDATED}.schema.json` |
| Task | `tasks/BNK.RLVR.CAP.SUP.002.BEN/TASK-002-foundation-mint-and-get-anchor.md` |

---

## TASK-005 — GDPR Art. 17 pseudonymisation (crypto-shred strategy)

`ADR-TECH-TACT-002` defers the key-management strategy to the implementer
and constrains only the **observable post-condition**: PII is not
recoverable from the database, `internal_id` survives, and downstream
foreign-key integrity is preserved.

The implementer's choice for TASK-005 (carried in `roadmap/OQ-2`):

### Per-anchor DEK (chosen)

- Every `anchor` row carries an FK `crypto_key_id` referencing
  `anchor_crypto_keys(crypto_key_id)`.
- `MINT_ANCHOR` provisions the DEK row (via `pgcrypto.gen_random_bytes(32)`
  for dev; via `hvac.Client.secrets.transit.create_key` in a real Vault
  deployment) **in the same transaction** as the anchor insert + outbox
  append. Either everything commits or nothing does.
- `PSEUDONYMISE_ANCHOR`:
  1. Wipes the four PII columns to NULL on the `anchor` row.
  2. `DELETE FROM anchor_crypto_keys WHERE crypto_key_id = $1` — the DEK
     row is gone.
  3. The FK `ON DELETE SET NULL` clause severs `anchor.crypto_key_id`;
     the same UPDATE writes NULL explicitly too (belt-and-suspenders).
  4. A `CHECK (anchor_status='PSEUDONYMISED' ⇒ all PII NULL AND
     crypto_key_id NULL)` constraint makes the (PSEUDONYMISED +
     non-null-PII) state **unforgeable at the database layer**.
- All four atomic mutations live in the same transaction (`PostgresUnitOfWork`).

### Why per-anchor, not per-zone or per-IS?

- **Blast-radius minimisation.** Shredding one DEK destroys exactly one
  anchor's recoverable PII; the other ten million anchors are
  untouched. Per-zone / per-IS keys would tie the durability of every
  anchor in the zone to that single key — disastrous if mis-rotated.
- **No retention sweep required.** Per-zone shredding is only safe if no
  un-pseudonymised anchor is left under the rotated key (you'd have to
  re-encrypt all the others before deleting the old key). Per-anchor
  has no such coupling.
- **Audit clarity.** Every PSEUDONYMISE leaves a one-row delete in
  `anchor_crypto_keys` keyed by the destroyed anchor — a trivial DBA-
  level audit query.

### Migration path to Vault transit (deferred)

The in-postgres `anchor_crypto_keys` table is a **dev-only** placeholder.
A production rollout swaps `PostgresCryptoKeyRepository` for a Vault-
transit-backed adapter (via `hvac`) — the port `CryptoKeyRepository`
stays unchanged, the wire and DB contracts (PII columns NULL,
`crypto_key_id` NULL, audit query) are unchanged. Vault transit gives:

- Cryptographic ratchet (each DEK encrypted under a master key that
  rotates).
- Hardware-backed master key (HSM via Vault transit auto-unseal).
- Centralised audit log (`vault audit list`).

The migration is **out of scope** for TASK-005 — see
`roadmap/OQ-3 — Vault transit deployment`.

### Joint-custody sign-off

The PII-touching DoD items (crypto-shred semantics, irreversibility,
DEK shredding) require **DPO + IT Security sign-off** in the PR
description per the roadmap risk matrix.
