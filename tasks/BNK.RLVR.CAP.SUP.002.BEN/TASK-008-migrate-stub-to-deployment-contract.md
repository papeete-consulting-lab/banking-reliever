---
task_id: TASK-008
capability_id: BNK.RLVR.CAP.SUP.002.BEN
bcm_ref: 9be9fe9
capability_name: Beneficiary Identity Anchor
epic: Epic — Deployment Contract Migration
status: in_progress
priority: medium
depends_on: []
loop_count: 1
max_loops: 10
---

# TASK-008 — Migrate stub to the Deployment contract

## Context

The Mode-B contract stub for **Beneficiary Identity Anchor**
(`BNK.RLVR.CAP.SUP.002.BEN`) was scaffolded before the **Deployment
contract (local + dev)** landed in CLAUDE.md (commit `ad1edee`,
2026-05-27). Its deployment artifacts live at the component root in the
legacy layout — bundled RabbitMQ, branch-derived random ports — which
the new contract replaces.

This is a **mechanical migration of the deployment shell only**. No source
code, dependencies, or runtime behaviour are touched.

## Capability Reference

- Capability: Beneficiary Identity Anchor (`BNK.RLVR.CAP.SUP.002.BEN`)
- Zone: `SUPPORT`
- Component: `stub/` (kind = `api`, Mode B contract+stub, Python / FastAPI)
- Governing contract: **CLAUDE.md § "Deployment contract (local + dev)"** — single source of truth.

## What to Build

Read the current state of `sources/BNK.RLVR.CAP.SUP.002.BEN/stub/` and emit
the new deployment artifacts per the Deployment contract:

1. **`stub/deployment/local/`**:
   - `Dockerfile` — moved from `stub/Dockerfile`. Keep the existing multi-stage Python build, the `RELIEVER_HTTP_HOST=0.0.0.0 / RELIEVER_HTTP_PORT=8000`, `EXPOSE 8000`, and the uvicorn entrypoint.
   - `docker-compose.yml` — runs ONLY the stub image; joins the external `reliever-platform` Docker network; no inline RabbitMQ. Healthcheck on `/health`.
   - `.env` — `COMPONENT_PORT=<deterministic>` (kind=`api`), `RELIEVER_HTTP_PORT=8000`, `RELIEVER_AMQP_URL=amqp://admin:password@rabbitmq:5672/`, plus any existing stub-specific env (publisher cadence, kill-switch).
   - `platform.compose.yml` — opt-in stand-in: external network + RabbitMQ on host 5672/15672 only (stub has no DB).
   - `README.md` — short usage note stating that the platform (or stand-in) is a prerequisite.

2. **`stub/deployment/dev/k8s/{base,overlay/dev}/`** — kustomize derived via `tech` from `runtime/deploy`, `runtime/api_ingress` (URL contract `https://k8s.<base>/{env}/BNK.RLVR.CAP.SUP.002.BEN/api/`), `identity/secrets` + `identity/workload`.

3. **`stub/deployment/dev/terraform/`** — banking-tech modules only, derived via `tech`. Stubs typically have no DB → minimal terraform root. If any needed resource has no module, open the escape-hatch issue at `Banking-PapeeteConsulting/banking-tech` and record the URL.

4. **Remove** the legacy root-level files: `stub/Dockerfile`, `stub/docker-compose.yml`.

5. **Append** to `/deployment/PORTS.md` the row `BNK.RLVR.CAP.SUP.002.BEN:api → <port>` for audit (kind=`api` — but note: this **collides** with TASK-007's backend in the same capability, both kind=`api`. Per CLAUDE.md, the audit-ledger collision rule kicks in: the second one to land re-hashes with salt `:1`. The backend is the primary; the stub salts. Document the salt in the PORTS.md row.)

## Scope guardrails — read carefully

This is a deployment-only re-emission on an EXISTING component. The agent
boundary "push back if output dir already populated" is **explicitly
overridden** for files under `deployment/`. Everything else stays untouched:

- ❌ DO NOT regenerate `src/`, `tests/`, `pyproject.toml`, `fixtures/`, or any application code.
- ❌ DO NOT renumber events, regenerate JSON Schemas, or alter the bus topology.
- ✅ ONLY create/replace files under `stub/deployment/`.
- ✅ If `config/*.toml` / settings references RabbitMQ with `localhost:{RABBIT_PORT}`, replace it with the service-name form (`amqp://...@rabbitmq:5672/`). Only the bus URL.

## Definition of Done

- [ ] `stub/deployment/local/` contains `Dockerfile`, `docker-compose.yml`, `.env`, `platform.compose.yml`, `README.md`.
- [ ] `stub/deployment/dev/k8s/{base,overlay/dev}/` exist with kustomize manifests derived via `tech`.
- [ ] `stub/deployment/dev/terraform/` exists with a banking-tech-modules-only root (escape-hatch GH issue URL recorded in its `README.md` if any resource has no module).
- [ ] Legacy root-level `Dockerfile` and `docker-compose.yml` removed.
- [ ] `/deployment/PORTS.md` records the deterministic `BNK.RLVR.CAP.SUP.002.BEN:api → <port>` row (with salt if collision against TASK-007's backend in the same capability).
- [ ] `docker compose -f stub/deployment/local/platform.compose.yml up -d` then `docker compose -f stub/deployment/local/docker-compose.yml up -d --build` succeed; `GET /health` returns 200 on the deterministic `COMPONENT_PORT`.
- [ ] Stage 5 test agent (`test-business-capability`) passes against the new paths.

## Acceptance Criteria (Business)

- **No behavioural change.** Same published events, same canned-fixture query responses, same routing keys, same publisher cadence. Only the deployment shell is reshaped.

## Dependencies

- **TASK-007** (backend migration) is the natural primary for `kind=api` in this capability — run it first so its port lands without salt. This stub migration salts on collision (rare but possible). The two can otherwise run in either order; they target different output dirs.
- Coordinate with the **"one active task per capability"** invariant against in-flight feature TASKs in `SUP.002.BEN` (TASK-005, TASK-006).

## Open Questions

- None.
