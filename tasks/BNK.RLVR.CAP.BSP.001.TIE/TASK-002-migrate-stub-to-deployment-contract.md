---
task_id: TASK-002
capability_id: BNK.RLVR.CAP.BSP.001.TIE
bcm_ref: 9be9fe9
capability_name: Tier Management
epic: Epic — Deployment Contract Migration
status: todo
priority: medium
depends_on: []
loop_count: 0
max_loops: 10
---

# TASK-002 — Migrate stub to the Deployment contract

## Context

The Mode-B contract stub for **Tier Management** (`BNK.RLVR.CAP.BSP.001.TIE`)
was scaffolded before the **Deployment contract (local + dev)** landed in
CLAUDE.md (commit `ad1edee`, 2026-05-27). Its deployment artifacts live at
the component root in the legacy layout — bundled RabbitMQ, branch-derived
random ports — which the new contract replaces.

This is a **mechanical migration of the deployment shell only**. No source
code, dependencies, or runtime behaviour are touched.

## Capability Reference

- Capability: Tier Management (`BNK.RLVR.CAP.BSP.001.TIE`)
- Zone: `BUSINESS_SERVICE_PRODUCTION`
- Component: `stub/` (kind = `api`, Mode B contract+stub, .NET 10)
- Governing contract: **CLAUDE.md § "Deployment contract (local + dev)"** — single source of truth.

## What to Build

Read the current state of `sources/BNK.RLVR.CAP.BSP.001.TIE/stub/` and emit
the new deployment artifacts per the Deployment contract:

1. **`stub/deployment/local/`**:
   - `Dockerfile` — the universal build (moved from component root if present, otherwise authored).
   - `docker-compose.yml` — runs ONLY the stub image; joins the external `reliever-platform` Docker network; no inline RabbitMQ.
   - `.env` — `COMPONENT_PORT=<deterministic>` (kind=`api`) + the RabbitMQ connection string in platform service-name form.
   - `platform.compose.yml` — opt-in stand-in: external network + RabbitMQ on host 5672/15672.
   - `README.md` — short usage note stating that the platform (or stand-in) is a prerequisite.

2. **`stub/deployment/dev/k8s/{base,overlay/dev}/`** — kustomize derived via `tech` from `runtime/deploy`, `runtime/api_ingress` (URL contract `https://k8s.<base>/{env}/BNK.RLVR.CAP.BSP.001.TIE/api/`), `identity/secrets` + `identity/workload`.

3. **`stub/deployment/dev/terraform/`** — banking-tech modules only, derived via `tech`. Stubs typically have no DB → minimal terraform root. If any needed resource has no module, open the escape-hatch issue at `Banking-PapeeteConsulting/banking-tech` and record the URL.

4. **Remove** the legacy `sources/BNK.RLVR.CAP.BSP.001.TIE/stub/docker-compose.yml`.

5. **Append** to `/deployment/PORTS.md` the row `BNK.RLVR.CAP.BSP.001.TIE:api → <port>` for audit.

## Scope guardrails — read carefully

This is a deployment-only re-emission on an EXISTING component. The agent
boundary "push back if output dir already populated" is **explicitly
overridden** for files under `deployment/`. Everything else stays untouched:

- ❌ DO NOT regenerate `src/`, `tests/`, `*.csproj`, `*.sln`, or any application code.
- ❌ DO NOT renumber events, regenerate JSON Schemas, or alter the bus topology.
- ✅ ONLY create/replace files under `stub/deployment/`.
- ✅ If `appsettings*.json` holds legacy `localhost:{RABBIT_PORT}` host-port strings, replace them with the platform service-name form (`@rabbitmq:5672`). Only the bus URL.

## Definition of Done

- [ ] `stub/deployment/local/` contains `Dockerfile`, `docker-compose.yml`, `.env`, `platform.compose.yml`, `README.md`.
- [ ] `stub/deployment/dev/k8s/{base,overlay/dev}/` exist with kustomize manifests derived via `tech`.
- [ ] `stub/deployment/dev/terraform/` exists with a banking-tech-modules-only root (escape-hatch GH issue URL recorded in its `README.md` if any resource has no module).
- [ ] Legacy root-level `docker-compose.yml` removed.
- [ ] `/deployment/PORTS.md` records the deterministic `BNK.RLVR.CAP.BSP.001.TIE:api → <port>` row.
- [ ] `docker compose -f stub/deployment/local/platform.compose.yml up -d` then `docker compose -f stub/deployment/local/docker-compose.yml up -d --build` succeed; `GET /health` returns 200 on the deterministic `COMPONENT_PORT`.
- [ ] Stage 5 test agent (`test-business-capability`) passes against the new paths.

## Acceptance Criteria (Business)

- **No behavioural change.** Same published events, same canned-fixture query responses, same routing keys. Only the deployment shell is reshaped.

## Dependencies

- None hard. The only existing TASK in this capability (TASK-001) is done — no in-flight feature TASK to coordinate against.

## Open Questions

- None.
