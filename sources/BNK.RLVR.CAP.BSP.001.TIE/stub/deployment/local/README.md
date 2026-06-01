# BNK.RLVR.CAP.BSP.001.TIE — Tier Management stub — local deployment

Per the Deployment contract (`CLAUDE.md` § *Deployment contract (local + dev)*),
this folder is the **universal build + the local-run shell** for the Mode-B
contract stub. The build artefact is reused by the dev environment (`deployment/dev/`)
via ECR.

## Prerequisites

A **Reliever platform installation** (or its stand-in) must already be up,
exposing RabbitMQ on the shared external Docker network `reliever-platform`.

If you don't have the real platform on your laptop, bring the stand-in up
once per session:

```bash
docker compose -f sources/BNK.RLVR.CAP.BSP.001.TIE/stub/deployment/local/platform.compose.yml up -d
```

This creates the `reliever-platform` network and runs RabbitMQ inside it
(AMQP on `rabbitmq:5672` service-name, Management UI on host `15672`).

## Run the stub

```bash
docker compose \
  -f sources/BNK.RLVR.CAP.BSP.001.TIE/stub/deployment/local/docker-compose.yml \
  up -d --build
```

| Endpoint                | URL                                |
|-------------------------|------------------------------------|
| Health                  | `http://localhost:20393/health`    |
| RabbitMQ Mgmt UI (stand-in only) | `http://localhost:15672` (guest/guest) |

Port `20393` is **deterministic** from the capability id + kind
(`sha256("BNK.RLVR.CAP.BSP.001.TIE:api")[:8] mod 9000 + 20000`) — same
value on every laptop and every branch. Audit ledger: `/deployment/PORTS.md`.

## Activate publication

The stub is **inactive by default** (DoD: inactive in production). To turn
publication on for a dev loop, override the env var:

```bash
STUB_Stub__Active=true \
  docker compose \
    -f sources/BNK.RLVR.CAP.BSP.001.TIE/stub/deployment/local/docker-compose.yml \
    up -d --build
```

Bus topology (unchanged — Mode-B contract is identical to the future engine):

| Item        | Value                                                                                  |
|-------------|----------------------------------------------------------------------------------------|
| Exchange    | `bsp.001.pal-events` (topic)                                                           |
| Routing key | `BNK.RLVR.EVT.BSP.001.TIER_UPGRADED.BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED`        |
| Cadence     | `STUB_Stub__EventsPerMinute` ∈ `[1,10]` (default 6) — outside requires the `Allow…` flag |

## Stop & clean up

```bash
docker compose -f sources/BNK.RLVR.CAP.BSP.001.TIE/stub/deployment/local/docker-compose.yml down
# Only if you're done with the platform stand-in:
docker compose -f sources/BNK.RLVR.CAP.BSP.001.TIE/stub/deployment/local/platform.compose.yml down -v
```

## Notes on the `/health` shim

The application is a pure `BackgroundService` (no Kestrel host in `src/`)
and TASK-002 forbids touching `src/`. To satisfy the Deployment contract
DoD (`GET /health` returns 200 on `COMPONENT_PORT`), the container runs
the .NET worker alongside a `socat`-based HTTP responder. The responder
reports `200 OK` iff the worker PID is alive, `503` otherwise — pure
liveness, no routing. Lives entirely under `deployment/local/`
(`entrypoint.sh`, `health-shim.sh`, `Dockerfile`).
