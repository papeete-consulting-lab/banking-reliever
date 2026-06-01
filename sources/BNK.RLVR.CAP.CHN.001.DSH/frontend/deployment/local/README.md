# BNK.RLVR.CAP.CHN.001.DSH — Frontend — local deployment

Deployment contract artefacts (CLAUDE.md § "Deployment contract (local + dev)")
for the Beneficiary Dashboard frontend, kind = `frontend`, vanilla HTML5/CSS3/JS
served by `nginx:alpine`.

## Files

| File | Owner | Notes |
|---|---|---|
| `Dockerfile` | universal | Multi-stage `alpine:3.20` → `nginx:alpine`. Same image is pulled from ECR by `deployment/dev/`. |
| `nginx.conf` | universal | SPA-friendly try_files, cache-headers, `/capabilities/...` → BFF reverse proxy. Stays unchanged across local and dev. |
| `docker-compose.yml` | local | Brings up the frontend ONLY, joins the external `reliever-platform` network. |
| `.env` | local | Deterministic `COMPONENT_PORT=22695`, sibling `BFF_ORIGIN` recorded for diagnostics. Committed-by-design. |
| `platform.compose.yml` | local (opt-in) | Stand-in platform: ext network + RabbitMQ on 5672/15672 (frontend needs no infra of its own; the broker is only for the sibling BFF). NOT the platform — only a stand-in for devs without it. |

## Prerequisite — platform

A real platform install OR the stand-in compose must be running first, so the
shared external Docker network `reliever-platform` exists and the BFF is
reachable by service name `chn-001-dsh-bff:8080`.

## Run

```bash
# (1) Stand-in platform — only needed if the real platform isn't installed.
docker compose -f sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/deployment/local/platform.compose.yml up -d

# (2) Sibling BFF — see sources/BNK.RLVR.CAP.CHN.001.DSH/bff/deployment/local/README.md.
docker compose -f sources/BNK.RLVR.CAP.CHN.001.DSH/bff/deployment/local/docker-compose.yml \
               --env-file sources/BNK.RLVR.CAP.CHN.001.DSH/bff/deployment/local/.env \
               up -d --build

# (3) The frontend — build context is the repo root.
docker compose -f sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/deployment/local/docker-compose.yml \
               --env-file sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/deployment/local/.env \
               up -d --build

# (4) Open the dashboard.
#     Nominal scenario:
xdg-open "http://localhost:22695/?beneficiaireId=BEN-001"
#     Consent refusal scenario:
xdg-open "http://localhost:22695/?beneficiaireId=BEN-001&consentement=refuse"
```

## Deterministic port

```
COMPONENT_PORT = 20000 + (int(sha256("BNK.RLVR.CAP.CHN.001.DSH:frontend").hexdigest()[:8], 16) % 9000)
              = 22695
```

Audit ledger: `/deployment/PORTS.md` (re-hash with `:1`, `:2`, … on cross-cap
collision, per the contract). Same capability + same kind → same port on every
branch and every laptop. The "one active task per capability" invariant
prevents intra-capability conflict.

## How the frontend reaches the BFF

The static bundle (`api.js`) issues **same-origin** fetches against the
relative path `/capabilities/chn/001/dsh/...`. The local `nginx.conf` ships
a reverse-proxy rule:

```
location /capabilities/ {
    proxy_pass http://chn-001-dsh-bff:8080;
    ...
}
```

So:

- the browser sees `http://localhost:22695/capabilities/...`, no CORS;
- nginx forwards to `chn-001-dsh-bff:8080` over the shared Docker network;
- the BFF responds; the browser sees the answer on the same origin.

`BFF_ORIGIN=http://localhost:22328` in `.env` is **diagnostic only** — the
nginx upstream uses the Docker service name, not the host port. The two are
the deterministic forms of the same component address (see
`sources/BNK.RLVR.CAP.CHN.001.DSH/bff/deployment/local/.env`).

In dev / prod, the URL contract from `ADR-TECH-STRAT-003`
(`https://k8s.<base>/{env}/<CAP_ID>/...`) is enforced at the ALB level — see
`deployment/dev/k8s/overlay/dev/ingress.yaml`. nginx still serves the static
files but does NOT do the reverse proxy in cluster mode (the ALB does it).

## Scope — what this layer does NOT touch

This is **first-time deployment scaffolding**. The static files (`index.html`,
`app.css`, `app.js`, `api.js`, `i18n.js`, `stub-data.js`, `dev.html`, the
component `README.md`) are unchanged. The dignity rule, consent gate, French
vocabulary, scenario coverage, stub-data fallback, branch badge, and
testability hooks all behave bit-identically to the pre-migration files. Only
a new image-based serving substrate is added; the legacy
`python -m http.server` dev story is superseded but not enforced.
