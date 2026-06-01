# BNK.RLVR.CAP.CHN.001.DSH — BFF — local deployment

Deployment contract artefacts (CLAUDE.md § "Deployment contract (local + dev)")
for the Beneficiary Dashboard BFF, kind = `bff`, .NET 10.

## Files

| File | Owner | Notes |
|---|---|---|
| `Dockerfile` | universal | Multi-stage `mcr.microsoft.com/dotnet/sdk:10.0 → aspnet:10.0`. Same image is pulled from ECR by `deployment/dev/`. |
| `docker-compose.yml` | local | Brings up the BFF ONLY, joins the external `reliever-platform` network. |
| `.env` | local | Deterministic `COMPONENT_PORT=22328`, platform service-name `AMQP_URL`, branch slug, CORS allowlist. Committed-by-design. |
| `platform.compose.yml` | local (opt-in) | Stand-in platform: ext network + RabbitMQ on 5672/15672. NOT the platform — only a stand-in for devs without it. |

## Prerequisite — platform

A real platform install OR the stand-in compose must be running first, so the
shared external Docker network `reliever-platform` exists and the broker is
reachable by service name `rabbitmq:5672`.

## Run

```bash
# (1) Stand-in platform (skip if real platform is up).
docker compose -f sources/BNK.RLVR.CAP.CHN.001.DSH/bff/deployment/local/platform.compose.yml up -d

# (2) The BFF — build context is the repo root.
docker compose -f sources/BNK.RLVR.CAP.CHN.001.DSH/bff/deployment/local/docker-compose.yml \
               --env-file sources/BNK.RLVR.CAP.CHN.001.DSH/bff/deployment/local/.env \
               up -d --build

# (3) Health probe.
curl -s http://localhost:22328/health | jq .
```

## Deterministic port

```
COMPONENT_PORT = 20000 + (int(sha256("BNK.RLVR.CAP.CHN.001.DSH:bff").hexdigest()[:8], 16) % 9000)
              = 22328
```

Audit ledger: `/deployment/PORTS.md` (re-hash with `:1`, `:2`, … on cross-cap
collision, per the contract). Same capability + same kind → same port on every
branch and every laptop. The "one active task per capability" invariant
prevents intra-capability conflict.

## Broker credentials

The committed `.env` ships `guest:guest` — the credentials the stand-in
`platform.compose.yml` exposes. If you are running against the **real**
laptop-platform install (e.g. a `platform-local-rabbitmq` container with
non-default credentials), override the broker creds at compose time without
mutating the committed `.env`, e.g.:

```bash
RabbitMQ__Username=platform RabbitMQ__Password=platform-local-dev \
docker compose -f sources/BNK.RLVR.CAP.CHN.001.DSH/bff/deployment/local/docker-compose.yml \
               --env-file sources/BNK.RLVR.CAP.CHN.001.DSH/bff/deployment/local/.env \
               up -d --build
```

Dev/prod resolve broker credentials via External Secrets per
`BNK.TECH.CAP.IDENTITY.001.SECRETS` (see `deployment/dev/k8s/overlay/dev/externalsecret.yaml`).

## Bus isolation

Exchange / queue **names** still carry the branch slug
(`task-007-migrate-bff-to-deployment-contract`) so concurrent worktrees on the
shared platform broker don't cross-talk. The bus URL only changed from
`localhost:6255` to `rabbitmq:5672` — topology is untouched.

## CORS

`CORS_ALLOWED_ORIGINS=http://localhost:22695` — the deterministic port of the
sibling frontend (`kind=frontend`, TASK-008 owner). Re-derived locally:

```python
import hashlib
FRONTEND_PORT = 20000 + (int(hashlib.sha256(b"BNK.RLVR.CAP.CHN.001.DSH:frontend").hexdigest()[:8], 16) % 9000)
# → 22695
```

## What changed vs. the legacy layout

| Before (TASK-002) | After (TASK-007) |
|---|---|
| `bff/Dockerfile` | `bff/deployment/local/Dockerfile` |
| `bff/docker-compose.yml` (bundles RabbitMQ) | `bff/deployment/local/docker-compose.yml` (BFF only, joins ext net) |
| `.env.local` (branch-derived random ports, gitignored) | `.env` (deterministic, committed-by-design) |
| `RABBIT_PORT = BFF_PORT + 100` | platform service name `rabbitmq:5672` |
| no platform stand-in | `platform.compose.yml` opt-in |

Source code, endpoints, consumers, ETag/304 contract, and bus topology are
unchanged.
