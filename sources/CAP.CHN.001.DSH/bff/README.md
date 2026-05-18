# CAP.CHN.001.DSH — Beneficiary Dashboard BFF

.NET 10 Minimal API Backend-For-Frontend (`create-bff` agent, TASK-002 of CAP.CHN.001.DSH).

This service is the unique HTTP entry point between the dashboard mobile frontend and the rest of the IS. It:

- Subscribes to three upstream resource events from CAP.BSP.001.SCO / CAP.BSP.001.TIE / CAP.BSP.004.ENV on producer-owned topic exchanges.
- Materialises one `AGG.CHN.001.DSH.BENEFICIARY_DASHBOARD` instance per `case_id` lazily on the first accepted command (INV.DSH.006), in-memory only.
- Enforces INV.DSH.001 (PII exclusion), INV.DSH.002 (idempotency on event_id), INV.DSH.003 (monotonic timestamps on score / tier), INV.DSH.005 (recent_transactions bounded at 50 / 30d).
- Serves `GET /capabilities/chn/001/dsh/cases/{case_id}/dashboard` with ETag/304 + `Cache-Control: private, max-age=5` (matches the 5s polling cadence prescribed by ADR-TECH-TACT-001).

Process contract: read-only at `process/CAP.CHN.001.DSH/`. Tactical anchor: ADR-TECH-TACT-001. Functional anchor: ADR-BCM-FUNC-0009.

## Run locally

```bash
# 1. Start RabbitMQ (branch-isolated host ports — see "Ports" below).
docker compose -f sources/CAP.CHN.001.DSH/bff/docker-compose.yml up -d

# 2. Run the BFF.
cd sources/CAP.CHN.001.DSH/bff
dotnet run --project src/Reliever.BeneficiaryDashboard.Bff

# 3. Health probe.
curl -s http://localhost:6155/health | jq .
# Expected:
# { "status": "ok", "capability": "CAP.CHN.001.DSH", "branch_slug": "task-002-bff-foundation-subscriptions-aggregate", ... }
```

## Ports (branch-deterministic)

This BFF is scaffolded inside the worktree of branch `feat/TASK-002-bff-foundation-subscriptions-aggregate`. Ports are derived deterministically from the branch slug so concurrent worktrees never collide:

```
BFF_PORT          = 6080 + sha256(slug)[0..8] % 100   = 6155
RABBIT_PORT       = BFF_PORT + 100                    = 6255
RABBIT_MGMT_PORT  = BFF_PORT + 101                    = 6256
FRONT_DEV_PORT    = BFF_PORT + 200                    = 6355  (reserved for sibling code-web-frontend agent)
```

The slug is the part of the branch name after `feat/`, lowercased. The base offset `6080` is chosen above the OS ephemeral-port range floor and below 6500 to avoid the upstream stub allocations (`bsp.001.tie-stub` uses 45381/45382; `bsp.001.sco-stub` uses its own range; `bsp.004.env-stub` uses its own range). All four values are captured in `.env.local` (gitignored) for `test-app` to discover.

## Subscription topology

Queue names carry the branch slug → multiple concurrent worktrees never share a queue. Exchange names are producer-owned and immutable.

| Subscription | Source exchange | Routing key (binding) | Queue (this branch) |
|--------------|-----------------|------------------------|----------------------|
| ON_SCORE_RECOMPUTED | `bsp.001.sco-events` | `EVT.BSP.001.SCORE_RECOMPUTED.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED` | `chn.001.dsh.q.score-recomputed-task-002-bff-foundation-subscriptions-aggregate` |
| ON_TIER_UPGRADE_RECORDED | `bsp.001.tie-events` | `EVT.BSP.001.TIER_UPGRADED.RVT.BSP.001.TIER_UPGRADE_RECORDED` | `chn.001.dsh.q.tier-upgraded-task-002-bff-foundation-subscriptions-aggregate` |
| ON_ENVELOPE_CONSUMPTION_RECORDED | `bsp.004.env-events` | `EVT.BSP.004.ENVELOPE_CONSUMED.RVT.BSP.004.CONSUMPTION_RECORDED` | `chn.001.dsh.q.envelope-consumed-task-002-bff-foundation-subscriptions-aggregate` |

DLQ: MassTransit's default `_error` queue convention — each receive-endpoint gets a `<queue>_error` sibling. Payload-shape and PII-classification violations throw from the consumer and land there. Idempotency hits and stale-event drops are ack-and-dropped silently (per `policies.yaml` error handling).

## HTTP surface

| Method | Path | Owner task | Status here |
|--------|------|-----------|-------------|
| GET | `/health` | — | wired |
| GET | `/capabilities/chn/001/dsh/cases/{case_id}/dashboard` | TASK-002 | wired, ETag/304 |
| GET | `/capabilities/chn/001/dsh/cases/{case_id}/transactions` | TASK-004 | 501 stub |
| POST | `/capabilities/chn/001/dsh/cases/{case_id}/dashboard-views` | TASK-005 (Epic 4) | 501 stub |

Bearer token handling is *dev-permissive* for TASK-002 (any well-formed JWT is accepted; the `sub` claim is recorded as actor when present, otherwise the request is treated as anonymous dev traffic). Production validation is wired by uncommenting the `AddAuthentication().AddJwtBearer(...)` block in `Program.cs` once the L2 tactical ADR specifies the issuer.

## Environment variables

| Var | Default | Purpose |
|-----|---------|---------|
| `ASPNETCORE_URLS` | `http://localhost:6155` | Bind address (set by `launchSettings.json`). |
| `ASPNETCORE_ENVIRONMENT` | `Development` | Drives `appsettings.{env}.json`. |
| `RabbitMQ__Host` | `localhost` | RabbitMQ host. |
| `RabbitMQ__Port` | `6255` (dev) / `5672` (prod) | AMQP port. |
| `RabbitMQ__VirtualHost` | `/` | See assumption A6. |
| `Bff__BranchSlug` | branch tail | Used to suffix queue names AND `environment` OTel tag. |
| `Telemetry__OtlpEndpoint` | unset in dev → console exporter; `http://localhost:4317` in prod | OTLP exporter. |
| `Telemetry__Environment` | branch slug | OTel `environment` resource attribute (ADR-TECH-STRAT-005). |

## Aggregate / projection

The aggregate IS the projection — no separate read store (per the Framing Decisions in `roadmap.md`). State fields, invariants, snapshotting policy and bounded-collection semantics mirror `process/CAP.CHN.001.DSH/aggregates.yaml` 1-to-1.

`AGG.BENEFICIARY_DASHBOARD` snapshot fields:

- `case_id` (identity)
- `current_tier_code`, `tier_upgraded_at`
- `current_score`, `score_recomputed_at`
- `open_envelopes[]` (`envelope_id`, `category`, `allocated_amount`, `consumed_amount`, `available_amount`, `currency`, `last_updated_at`)
- `recent_transactions[]` (bounded 50 / 30d, FIFO on `recorded_at`)
- `last_viewed_at` (TASK-005 / Epic 4)
- `last_processed_event_ids` (bounded set — INV.DSH.002)

ETag is a sha-256 prefix over the canonical state — deterministic for equivalent state, advances on every accepted mutation, unchanged on idempotency / stale-event drops.

## Stub coexistence

The `sources/CAP.CHN.001.DSH/` capability folder may host a TASK-001 contract stub (for the future `RVT.CHN.001.DASHBOARD_VIEWED` emission). That stub is independent: it lives at `sources/CAP.CHN.001.DSH/stub/` and runs on its own ports. As of TASK-002, the stub does not yet exist on disk — TASK-001 is open. When it lands, both can run in parallel; the BFF will replace the stub's HTTP surface for endpoints it covers (currently `GET /dashboard` only — `POST /dashboard-views` and `GET /transactions` remain stubbed at 501 here until TASK-005 / TASK-004).

## Tests

```bash
cd sources/CAP.CHN.001.DSH/bff
dotnet test
```

- **Unit tests** (always run) cover INV.DSH.001 / 002 / 003 / 005, schema validation,
  ETag determinism, JWT actor extraction, store lazy materialisation.
- **Integration tests** (Docker-gated — Skip="…" by default) bring up RabbitMQ via Testcontainers,
  spin up the BFF in-process, publish synthetic RVTs, and assert end-to-end behaviour. Remove the
  `Skip = "..."` annotation on `DashboardEndToEndTests` to enable them locally.

## Assumptions (load-bearing — flag during review)

| # | Assumption | Justification | Owner to confirm |
|---|------------|---------------|------------------|
| A1 | No persistence — aggregate state is in-memory only. `SnapshotEveryNEvents` is a counter hook with no I/O. | Roadmap framing decision: "the aggregate IS the projection — no separate read store"; `aggregates.yaml.snapshotting` declared but persistence path deferred to TASK-006 (real-core handoff & operability). | TASK-006 |
| A2 | JWT signature is NOT verified by the BFF in TASK-002. We decode the bearer token and read `sub` as the actor; any well-formed JWT is accepted. | ADR-TECH-STRAT-003 bi-layer: gateway validates upstream; channel re-extracts the actor. Production wiring is a one-liner (`AddAuthentication().AddJwtBearer(...)`) once the L2 tactical ADR specifies the issuer / audience / JWKS endpoint. | L2 tactical ADR |
| A3 | Ports derive from `6080 + sha256(slug)[0:8] % 100`. The branch-tail slug also suffixes all queue names. Frontend dev port reserved at `BFF_PORT + 200` to coordinate with the sibling `code-web-frontend` agent. | Determinism in concurrent-worktree mode (`/launch-task auto`). Captured in `.env.local`. | — |
| A4 | For SCO, the idempotency key on the dashboard side is `envelope.message_id` (UUIDv7 of the RVT), NOT `trigger.event_id`. The upstream schema's `trigger.event_id` is the per-trigger id (the *upstream* RVT that drove the recomputation), not the SCO RVT id. Using `envelope.message_id` is the correct fanned-out idempotency key at the consumer. | Reading `process/CAP.BSP.001.SCO/schemas/RVT.BSP.001.CURRENT_SCORE_RECOMPUTED.schema.json` — `trigger.event_id` is causation, `envelope.message_id` is the RVT identity per ADR-TECH-STRAT-007. For TIE and ENV the schema ships `event_id` at the top level — we use that directly. | Producer roadmaps |
| A5 | `RVT.BSP.004.CONSUMPTION_RECORDED` does not carry `allocated_amount` / `currency` / `merchant_label` today. We derive `allocated_amount = consumed_amount_after + remaining_amount`, default `currency = "EUR"`, and record `merchant_label = null`. | The upstream schema (`process/CAP.BSP.004.ENV/schemas/…`) is the contract. `policies.yaml.ON_ENVELOPE_CONSUMPTION_RECORDED.open_question` already flags this gap; the BFF fails gracefully and surfaces the missing fields as nulls. | CAP.BSP.004.ENV roadmap |
| A6 | We use the default RabbitMQ vhost `/`. No per-capability vhost is created. | Simplicity-first; branch isolation comes from queue suffixes. Exchange names are producer-owned and shared with upstream stubs (which also use `/`). | — |

## Compliance summary

- INV.DSH.001 — PII exclusion: enforced by `PiiClassificationScanner` on every inbound payload (DLQ on hit) + low-PII state model.
- INV.DSH.002 — idempotency: `BoundedSet` of upstream event ids (200 entries / 30d) per aggregate.
- INV.DSH.003 — monotonicity: score / tier `*_at` compared with locally observed `*_at`; older is ack-and-dropped (no DLQ).
- INV.DSH.005 — recent_transactions bounded 50 / 30d, FIFO on `recorded_at`.
- INV.DSH.006 — lazy materialisation via `IDashboardAggregateStore.GetOrCreate`.
- ADR-TECH-STRAT-001: producer-owned exchanges + consumer-owned queues; at-least-once + idempotent consumers; DLQ on shape errors.
- ADR-TECH-STRAT-003: ETag on every GET; `Cache-Control: private, max-age=5`; bearer-token actor extraction (channel-side check).
- ADR-TECH-STRAT-005: OTel resource attributes `capability_id` / `zone` / `deployable` / `environment` (branch slug); per-policy ingest counter; per-subscription DLQ counter; spans inbound RVT → policy → command → aggregate.
- ADR-TECH-STRAT-007: UUIDv7 envelopes carried-through (RVT identity = `envelope.message_id`).
- ADR-TECH-TACT-001: .NET 10 BFF, ETag + 5s polling, PII exclusion.
- ADR-BCM-FUNC-0009: PII-free dashboard, dignity-encoded read model (rendered by the sibling frontend agent — out of BFF scope).
