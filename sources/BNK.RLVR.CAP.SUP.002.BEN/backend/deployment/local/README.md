# BNK.RLVR.CAP.SUP.002.BEN — backend — local deployment

Per the **Deployment contract** in `CLAUDE.md` (root), this folder owns the
LOCAL runtime of the Mode-A microservice for **Beneficiary Identity Anchor**
(`BNK.RLVR.CAP.SUP.002.BEN`). The platform (RabbitMQ + the per-L2 Postgres)
is **out of scope** — the component compose joins the shared external
network `reliever-platform` and reaches the broker and database by service
name (`rabbitmq`, `postgres`).

## Prerequisite — platform must be up

Either the real platform installation provides `rabbitmq` and `postgres`
on the `reliever-platform` network with the `beneficiary_anchor` database
pre-created, or stand up the in-folder stand-in:

```bash
docker compose -f platform.compose.yml up -d
```

This brings:

- RabbitMQ (`admin`/`password`) on host ports `5672` (AMQP) and `15672`
  (Management UI: <http://localhost:15672>).
- Postgres 16 with `POSTGRES_USER=reliever`, `POSTGRES_PASSWORD=reliever`,
  `POSTGRES_DB=beneficiary_anchor` on host port `5432`.

The stand-in is **explicitly not the platform** — it exists only for dev
convenience and the test agent.

## Run the component

```bash
docker compose --env-file .env -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml logs -f backend
```

The container applies migrations from `/app/migrations/` at startup, opens
the Postgres pool, declares the `sup.002.ben-events` topic exchange + its
queue (with the branch-tagged name for bus isolation), and starts the
outbox relay loop. Then `GET /health` returns 200 on the deterministic
`COMPONENT_PORT`:

```bash
curl -s http://localhost:26835/health | jq .
```

## Deterministic component port

| Capability                  | Kind | Port  |
|-----------------------------|------|-------|
| `BNK.RLVR.CAP.SUP.002.BEN`  | api  | 26835 |

Computed from `sha256("BNK.RLVR.CAP.SUP.002.BEN:api")[:8] % 9000 + 20000`.
Same capability + same kind → same port across every branch and every
laptop. See `/deployment/PORTS.md` for the cross-capability audit ledger.

The container's INTERNAL port stays 8000 (uvicorn default); the host
binding to 26835 is in `docker-compose.yml`.

## Bus isolation across worktrees

`BRANCH` in `.env` defaults to the current branch slug
(`task-007-migrate-backend-to-deployment-contract`). It is carried into:

- **Queue names** — so two concurrent worktrees on the same broker never
  cross-consume.
- **The OTel `environment` tag** — so traces / metrics are attributable
  to a branch.

Exchange names are producer-owned and remain shared (`sup.002.ben-events`)
so downstream stubs see the same topology regardless of branch.

## Tear down

```bash
docker compose -f docker-compose.yml          down
docker compose -f platform.compose.yml down -v   # also wipes the broker + DB volumes
```

## Where everything lives

| Path                          | Purpose                                                       |
|-------------------------------|---------------------------------------------------------------|
| `Dockerfile`                  | Universal image build — also pulled by dev (ECR)              |
| `docker-compose.yml`          | Component-only compose; joins external `reliever-platform`    |
| `.env`                        | Deterministic `COMPONENT_PORT` + service-name URLs            |
| `platform.compose.yml`        | Optional stand-in for the platform (RabbitMQ + Postgres)      |
| `README.md`                   | This file                                                     |

## Migration context

This layout REPLACES the legacy root-level `backend/Dockerfile` +
`backend/docker-compose.yml` (which bundled Postgres + RabbitMQ inline on
host ports 9043/9054/9080). TASK-007 removes those legacy files and
re-emits the component under the Deployment contract — same source code,
same migrations, same emitted events, same OTel tags. Only the deployment
shell is reshaped.
