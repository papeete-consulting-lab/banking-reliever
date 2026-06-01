# BNK.RLVR.CAP.BSP.001.SCO contract+stub — local deployment

Per the **Deployment contract** in `CLAUDE.md` (root), this folder owns the
LOCAL runtime of the Mode-B contract+stub for **Behavioural Scoring**
(`BNK.RLVR.CAP.BSP.001.SCO`). The platform (RabbitMQ) is **out of scope** —
the component compose joins the shared external network `reliever-platform`
and reaches the broker by service name `rabbitmq`.

## Prerequisite — platform must be up

Either the real platform installation provides `rabbitmq` on the
`reliever-platform` network, or stand up the in-folder stand-in:

```bash
docker compose -f platform.compose.yml up -d
```

This brings RabbitMQ (`guest`/`guest`) up on host ports `5672` (AMQP) and
`15672` (Management UI: http://localhost:15672). The stand-in is
**explicitly not the platform** — it exists only for dev convenience and
the test agent.

## Run the component

```bash
docker compose -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml logs -f bsp-sco-stub
```

The stub starts publishing synthetic RVT.* events at
`STUB_CADENCE_PER_MIN=6` (combined). Bind a queue to exchange
`bsp.001.sco-events` with routing key
`BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED.#` or
`BNK.RLVR.EVT.BSP.001.SCORE_THRESHOLD_REACHED.#` in the Management UI to
observe them.

## Liveness

The stub is a **pure RabbitMQ publisher** — it has no HTTP server, so the
container healthcheck probes the AMQP socket via a Python one-liner
(`socket.create_connection((rabbitmq, 5672), 2)`) instead of `GET /health`.
`docker compose ps` reports `healthy` once RabbitMQ accepts the
connection.

> The deterministic `COMPONENT_PORT` for `BNK.RLVR.CAP.BSP.001.SCO:api` is
> `23074` (see `/deployment/PORTS.md`). It is documented in `.env` and
> reserved in `Dockerfile`'s `EXPOSE` directive for cross-component
> uniformity, but **not** bound to the host — this stub has no HTTP
> surface.

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
| `.env`                        | Deterministic `COMPONENT_PORT` + `RABBITMQ_URL` (service name)|
| `platform.compose.yml`        | Optional stand-in for the platform (RabbitMQ only)            |
| `README.md`                   | This file                                                     |
