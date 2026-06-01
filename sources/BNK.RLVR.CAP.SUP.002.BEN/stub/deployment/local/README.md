# BNK.RLVR.CAP.SUP.002.BEN — stub — local deployment

Per the **Deployment contract** in `CLAUDE.md` (root), this folder owns the
LOCAL runtime of the **Mode-B contract+stub** for **Beneficiary Identity
Anchor** (`BNK.RLVR.CAP.SUP.002.BEN`). The platform (RabbitMQ) is **out of
scope** — the stub compose joins the shared external network
`reliever-platform` and reaches the broker by service name (`rabbitmq`).
The stub has **no database** — it serves canned fixtures from `fixtures/`.

> **Note** — Downstream consumers should target the **real microservice**
> under `../backend/` for `MINT` (`POST /anchors`) and `GET` paths. This
> stub remains the contract-snapshot source for the lifecycle transitions
> (`UPDATED`, `ARCHIVED`, `RESTORED`, `PSEUDONYMISED`) until the matching
> backend tasks ship.

## Prerequisite — platform must be up

Either the real platform installation provides `rabbitmq` on the
`reliever-platform` network, or stand up the in-folder stand-in:

```bash
docker compose -f platform.compose.yml up -d
```

This brings RabbitMQ (`admin`/`password`) on host ports `5672` (AMQP) and
`15672` (Management UI: <http://localhost:15672>). The stand-in is
**explicitly not the platform** — it exists only for dev convenience and
the test agent.

## Run the stub

```bash
docker compose --env-file .env -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml logs -f stub
```

The container loads the canned fixtures at startup, declares the
`sup.002.ben-events` topic exchange + its queue (branch-tagged for bus
isolation), and starts the synthetic publisher loop when
`RELIEVER_STUB_ACTIVE=true`. Then `GET /health` returns 200 on the
deterministic `COMPONENT_PORT`:

```bash
curl -s http://localhost:21595/health | jq .
curl -i  http://localhost:21595/anchors/018f8e10-0000-7000-8000-000000000001
```

## Deterministic component port

| Capability                  | Kind | Salt | Port  |
|-----------------------------|------|------|-------|
| `BNK.RLVR.CAP.SUP.002.BEN`  | api  | `:1` | 21595 |

Computed from `sha256("BNK.RLVR.CAP.SUP.002.BEN:api:1")[:8] % 9000 + 20000`.
The **salt-free** allocation (`26835`) is taken by the **TASK-007** backend
in the same capability (full Mode-A microservice — also `kind=api`). Per
the CLAUDE.md collision rule, the stub re-hashes with salt `:1` and records
the salt in `/deployment/PORTS.md`. Same capability + same kind + same salt
→ same port across every branch and every laptop.

The container's INTERNAL port stays 8000 (uvicorn default); the host binding
to 21595 is in `docker-compose.yml`.

## Bus isolation across worktrees

`BRANCH` in `.env` defaults to the current branch slug
(`task-008-migrate-stub-to-deployment-contract`). It is carried into:

- **Queue names** — so two concurrent worktrees on the same broker never
  cross-consume.
- **The OTel `environment` tag** — so traces / metrics are attributable
  to a branch.

Exchange names are producer-owned and remain shared (`sup.002.ben-events`)
so the real backend and this stub publish into the same topic exchange.

## Tear down

```bash
docker compose -f docker-compose.yml          down
docker compose -f platform.compose.yml down -v   # also wipes the broker volume
```

## Where everything lives

| Path                          | Purpose                                                       |
|-------------------------------|---------------------------------------------------------------|
| `Dockerfile`                  | Universal image build — also pulled by dev (ECR)              |
| `docker-compose.yml`          | Component-only compose; joins external `reliever-platform`    |
| `.env`                        | Deterministic `COMPONENT_PORT` (21595, salt=:1) + service-name URLs |
| `platform.compose.yml`        | Optional stand-in for the platform (RabbitMQ only — no DB)    |
| `README.md`                   | This file                                                     |

## Migration context

This layout REPLACES the legacy root-level `stub/Dockerfile` +
`stub/docker-compose.yml` (which bundled RabbitMQ inline on host ports
`54879`/`54880` and pinned the stub itself to `54679`). TASK-008 removes
those legacy files and re-emits the component under the Deployment
contract — same source code, same fixtures, same emitted events
(`BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED`), same routing keys,
same publisher cadence. Only the deployment shell is reshaped.
