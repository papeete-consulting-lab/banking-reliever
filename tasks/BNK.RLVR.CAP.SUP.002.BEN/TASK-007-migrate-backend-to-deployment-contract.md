---
task_id: TASK-007
capability_id: BNK.RLVR.CAP.SUP.002.BEN
bcm_ref: 9be9fe9
capability_name: Beneficiary Identity Anchor
epic: Epic — Deployment Contract Migration
status: todo
priority: medium
depends_on: []
loop_count: 0
max_loops: 10
---

# TASK-007 — Migrate backend to the Deployment contract

## Context

The Mode-A microservice backend for **Beneficiary Identity Anchor**
(`BNK.RLVR.CAP.SUP.002.BEN`) was scaffolded before the **Deployment
contract (local + dev)** landed in CLAUDE.md (commit `ad1edee`,
2026-05-27). Its deployment artifacts live at the component root in the
legacy layout — bundled Postgres + RabbitMQ, branch-derived random
ports — which the new contract replaces with a deterministic
`COMPONENT_PORT` and a component-only compose on the external
`reliever-platform` network.

This is a **mechanical migration of the deployment shell only**. No source
code, dependencies, or runtime behaviour are touched. `uv.lock` (newly
tracked in commit `11c700e`) stays committed; the Dockerfile builds
against it for reproducible image builds.

## Capability Reference

- Capability: Beneficiary Identity Anchor (`BNK.RLVR.CAP.SUP.002.BEN`)
- Zone: `SUPPORT`
- Component: `backend/` (kind = `api`, Mode A full microservice, Python 3.12+ / FastAPI / psycopg)
- Governing contract: **CLAUDE.md § "Deployment contract (local + dev)"** — single source of truth.

## What to Build

Read the current state of `sources/BNK.RLVR.CAP.SUP.002.BEN/backend/` and
emit the new deployment artifacts per the Deployment contract:

1. **`backend/deployment/local/`**:
   - `Dockerfile` — moved from `backend/Dockerfile`. Keep the existing multi-stage `python:3.12-slim` build, the `uv`-based dep install against the tracked `uv.lock`, the `RELIEVER_HTTP_HOST=0.0.0.0 / RELIEVER_HTTP_PORT=8000`, `EXPOSE 8000`, and the `uvicorn` entrypoint.
   - `docker-compose.yml` — runs ONLY the backend image; joins the external `reliever-platform` Docker network; no inline Postgres or RabbitMQ. Healthcheck on `/health`.
   - `.env` — `COMPONENT_PORT=<deterministic>` (kind=`api`), `RELIEVER_HTTP_HOST=0.0.0.0`, `RELIEVER_HTTP_PORT=8000`, `RELIEVER_PG_DSN=postgresql://reliever:reliever@postgres:5432/beneficiary_anchor`, `RELIEVER_AMQP_URL=amqp://admin:password@rabbitmq:5672/`, plus the existing branch and OTel keys.
   - `platform.compose.yml` — opt-in stand-in: external network + RabbitMQ on host 5672/15672 + Postgres on host 5432 (with `POSTGRES_DB=beneficiary_anchor`, `POSTGRES_USER=reliever`, `POSTGRES_PASSWORD=reliever` for parity with the existing dev creds).
   - `README.md` — short usage note stating that the platform (or stand-in) is a prerequisite.

2. **`backend/deployment/dev/k8s/{base,overlay/dev}/`** — kustomize derived via `tech` from `runtime/deploy` (namespace + PodSecurity + Quotas), `runtime/api_ingress` (Ingress with URL contract `https://k8s.<base>/{env}/BNK.RLVR.CAP.SUP.002.BEN/api/`), `identity/secrets` + `identity/workload` (ServiceAccount + IRSA + External Secrets for the DB password).

3. **`backend/deployment/dev/terraform/`** — banking-tech modules only, derived via `tech`. The TECH-TACT ADR (`ADR-TECH-TACT-002`) tags `postgresql` → resolve to `data/db` (RDS Postgres per ADR-TECH-STRAT-004 Rule 2). RabbitMQ is NOT provisioned here (platform-level `data/broker`). If any needed resource has no module, open the escape-hatch issue at `Banking-PapeeteConsulting/banking-tech` and record the URL.

4. **Remove** the legacy root-level files: `backend/Dockerfile`, `backend/docker-compose.yml`.

5. **Append** to `/deployment/PORTS.md` the row `BNK.RLVR.CAP.SUP.002.BEN:api → <port>` for audit.

## Scope guardrails — read carefully

This is a deployment-only re-emission on an EXISTING component. The agent
boundary "push back if output dir already populated" is **explicitly
overridden** for files under `deployment/`. Everything else stays untouched:

- ❌ DO NOT regenerate `src/`, `tests/`, `pyproject.toml`, `uv.lock`, `migrations/`, or any application code.
- ❌ DO NOT alter the bus topology, the schema-validation pipeline, the OTel instrumentation, the migrations, or the GDPR / state-machine guards.
- ✅ ONLY create/replace files under `backend/deployment/`.
- ✅ If `config/*.toml` or `settings.py` references Postgres or RabbitMQ with `localhost:{DB_PORT}` / `localhost:{RABBIT_PORT}` host-port strings, replace them with the service-name form (`postgres:5432`, `rabbitmq:5672`). Only the URL strings — no code change.

## Definition of Done

- [ ] `backend/deployment/local/` contains `Dockerfile`, `docker-compose.yml`, `.env`, `platform.compose.yml`, `README.md`.
- [ ] `backend/deployment/dev/k8s/{base,overlay/dev}/` exist with kustomize manifests derived via `tech`.
- [ ] `backend/deployment/dev/terraform/` exists with a banking-tech-modules-only root calling `data/db` for Postgres (escape-hatch GH issue URL recorded in its `README.md` if any resource has no module).
- [ ] Legacy root-level `Dockerfile` and `docker-compose.yml` removed.
- [ ] `/deployment/PORTS.md` records the deterministic `BNK.RLVR.CAP.SUP.002.BEN:api → <port>` row.
- [ ] `docker compose -f backend/deployment/local/platform.compose.yml up -d` then `docker compose -f backend/deployment/local/docker-compose.yml up -d --build` succeed; `GET /health` returns 200 on the deterministic `COMPONENT_PORT`.
- [ ] Stage 5 test agent (`test-business-capability`) passes against the new paths.

## Acceptance Criteria (Business)

- **No behavioural change.** Same REST endpoints (mint / get / update / archive / restore / pseudonymise / history), same emitted events, same OTel tags, same migrations applied at startup. Only the deployment shell is reshaped.

## Dependencies

- None hard. Sibling stub migration is **TASK-008** in this capability; they target different output dirs and can run in either order. Coordinate with the **"one active task per capability"** invariant against in-flight feature TASKs in `SUP.002.BEN` (TASK-005, TASK-006 are not done as of 2026-06-01).

## Open Questions

- None.
