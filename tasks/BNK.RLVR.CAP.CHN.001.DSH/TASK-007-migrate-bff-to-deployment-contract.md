---
task_id: TASK-007
capability_id: BNK.RLVR.CAP.CHN.001.DSH
bcm_ref: 9be9fe9
capability_name: Beneficiary Dashboard
epic: Epic — Deployment Contract Migration
status: done
priority: medium
depends_on: []
loop_count: 1
max_loops: 10
pr_url: https://github.com/Banking-PapeeteConsulting/banking-reliever/pull/31
---

# TASK-007 — Migrate BFF to the Deployment contract

## Context

The BFF for **Beneficiary Dashboard** (`BNK.RLVR.CAP.CHN.001.DSH`) was
scaffolded before the **Deployment contract (local + dev)** landed in
CLAUDE.md (commit `ad1edee`, 2026-05-27). Its deployment artifacts live at
the component root in the legacy layout:

- `sources/BNK.RLVR.CAP.CHN.001.DSH/bff/Dockerfile`
- `sources/BNK.RLVR.CAP.CHN.001.DSH/bff/docker-compose.yml` (bundles RabbitMQ inline)
- `sources/BNK.RLVR.CAP.CHN.001.DSH/bff/.env.local` (branch-derived random ports)

The new contract replaces all three with a single deterministic
`COMPONENT_PORT` per `capability_id + kind`, a component-only compose on
the external `reliever-platform` network, and a committed-by-design
`deployment/local/.env`.

This is a **mechanical migration of the deployment shell only**. No source
code, dependencies, or runtime behaviour are touched.

## Capability Reference

- Capability: Beneficiary Dashboard (`BNK.RLVR.CAP.CHN.001.DSH`)
- Zone: `CHANNEL`
- Component: `bff/` (kind = `bff`, .NET 10 ASP.NET Core Minimal API)
- Governing contract: **CLAUDE.md § "Deployment contract (local + dev)"** — single source of truth.

## What to Build

Read the current state of `sources/BNK.RLVR.CAP.CHN.001.DSH/bff/` and emit
the new deployment artifacts per the Deployment contract:

1. **`bff/deployment/local/`**:
   - `Dockerfile` — moved from `bff/Dockerfile`. Keep the existing multi-stage `mcr.microsoft.com/dotnet/sdk:10.0 → aspnet:10.0` build, the `ASPNETCORE_URLS=http://+:8080`, `EXPOSE 8080`, and the `capability_id` / `zone` / `deployable` labels.
   - `docker-compose.yml` — runs ONLY the BFF image; joins the external `reliever-platform` Docker network; no inline RabbitMQ. Healthcheck on `/health`.
   - `.env` — `COMPONENT_PORT=<deterministic>` (kind=`bff`), `AMQP_URL=amqp://guest:guest@rabbitmq:5672/`, `BRANCH=<slug>`, `CORS_ALLOWED_ORIGINS=http://localhost:<frontend port>` (re-derived with kind=`frontend` per the deterministic helper — sibling frontend TASK-008 owns that allocation but the BFF must allowlist it).
   - `platform.compose.yml` — opt-in stand-in: external network + RabbitMQ on host 5672/15672 only (BFF has no database).
   - `README.md` — short usage note stating that the platform (or stand-in) is a prerequisite.

2. **`bff/deployment/dev/k8s/{base,overlay/dev}/`** — kustomize derived via `tech` from `runtime/bff` (BFF runtime Deployment), `runtime/api_ingress` (Ingress with URL contract `https://k8s.<base>/{env}/BNK.RLVR.CAP.CHN.001.DSH/api/`), `runtime/deploy` (namespace + PodSecurity + Quotas), `identity/secrets` + `identity/workload`.

3. **`bff/deployment/dev/terraform/`** — banking-tech modules only, derived via `tech`. The BFF has no DB → typically a thin root referencing `runtime/bff` + `identity/*`. If any needed resource has no module, open the escape-hatch issue at `Banking-PapeeteConsulting/banking-tech` and record the URL.

4. **Remove** legacy root-level files: `bff/Dockerfile`, `bff/docker-compose.yml`, `bff/.env.local`.

5. **Append** to `/deployment/PORTS.md` the row `BNK.RLVR.CAP.CHN.001.DSH:bff → <port>` for audit.

## Scope guardrails — read carefully

This is a deployment-only re-emission on an EXISTING component. The agent
boundary "push back if output dir already populated" is **explicitly
overridden** for files under `deployment/`. Everything else stays untouched:

- ❌ DO NOT regenerate `src/`, `tests/`, `*.csproj`, `*.sln`, endpoints, consumers, or domain code.
- ❌ DO NOT alter the bus topology, exchange/queue naming (branch-slug prefix stays), or the ETag / state-cache logic.
- ✅ ONLY create/replace files under `bff/deployment/`.
- ✅ If `appsettings*.json` references RabbitMQ with `localhost:{RABBIT_PORT}`, replace it with the service-name form (`amqp://...@rabbitmq:5672/`). Only the bus URL.

## Definition of Done

- [ ] `bff/deployment/local/` contains `Dockerfile`, `docker-compose.yml`, `.env`, `platform.compose.yml`, `README.md`.
- [ ] `bff/deployment/dev/k8s/{base,overlay/dev}/` exist with kustomize manifests derived via `tech`.
- [ ] `bff/deployment/dev/terraform/` exists with a banking-tech-modules-only root (escape-hatch GH issue URL recorded in its `README.md` if any resource has no module).
- [ ] Legacy root-level files removed: `Dockerfile`, `docker-compose.yml`, `.env.local`.
- [ ] `/deployment/PORTS.md` records the deterministic `BNK.RLVR.CAP.CHN.001.DSH:bff → <port>` row.
- [ ] `docker compose -f bff/deployment/local/platform.compose.yml up -d` then `docker compose -f bff/deployment/local/docker-compose.yml up -d --build` succeed; `GET /health` returns 200 on the deterministic `COMPONENT_PORT`.
- [ ] CORS allowlist accepts the deterministic frontend port (re-derived locally, kind=`frontend`).
- [ ] Stage 5 test agent (`test-app`) passes against the new paths.

## Acceptance Criteria (Business)

- **No behavioural change.** Same L3 endpoints, same event consumers, same state cache, same ETag/304 contract. Only the deployment shell is reshaped.

## Dependencies

- None hard. Sibling frontend migration is **TASK-008** in this capability; the two can run in either order. Coordinate with the **"one active task per capability"** invariant against in-flight feature TASKs in `CHN.001.DSH`.

## Open Questions

- None.
