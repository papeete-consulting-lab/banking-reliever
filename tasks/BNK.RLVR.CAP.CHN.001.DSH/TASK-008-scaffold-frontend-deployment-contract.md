---
task_id: TASK-008
capability_id: BNK.RLVR.CAP.CHN.001.DSH
bcm_ref: 9be9fe9
capability_name: Beneficiary Dashboard
epic: Epic — Deployment Contract Migration
status: done
priority: medium
depends_on: []
loop_count: 0
max_loops: 10
pr_url: https://github.com/Banking-PapeeteConsulting/banking-reliever/pull/34
---

# TASK-008 — Scaffold frontend deployment under the Deployment contract

## Context

The vanilla web frontend for **Beneficiary Dashboard**
(`BNK.RLVR.CAP.CHN.001.DSH`) has **no deployment artifacts today** — it
ships as static HTML/CSS/JS files only. The new **Deployment contract
(local + dev)** in CLAUDE.md (commit `ad1edee`, 2026-05-27) gives every
component a real image and a kustomize+terraform dev layer; for the
frontend that means an `nginx:alpine` image serving the static files on
a deterministic port and a `runtime/static_hosting` dev hosting target.

This is **first-time scaffolding** of the deployment shell — there is
nothing to migrate from. The static files themselves are not touched.

## Capability Reference

- Capability: Beneficiary Dashboard (`BNK.RLVR.CAP.CHN.001.DSH`)
- Zone: `CHANNEL`
- Component: `frontend/` (kind = `frontend`, vanilla HTML5 / CSS3 / JS)
- Governing contract: **CLAUDE.md § "Deployment contract (local + dev)"** — single source of truth.

## What to Build

Author the deployment artifacts under `sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/deployment/` per the contract:

1. **`frontend/deployment/local/`**:
   - `Dockerfile` — multi-stage: stage 1 copies the static files, stage 2 `FROM nginx:alpine`, copies the static files to `/usr/share/nginx/html`, copies `nginx.conf` to `/etc/nginx/conf.d/default.conf`, `EXPOSE 80`.
   - `nginx.conf` — SPA-friendly: `try_files $uri $uri/ /index.html`, sensible cache headers (long-cache for hashed assets, no-cache for `index.html`).
   - `docker-compose.yml` — runs ONLY the nginx image; joins the external `reliever-platform` Docker network; healthcheck on `GET /`.
   - `.env` — `COMPONENT_PORT=<deterministic>` (kind=`frontend`), `BFF_ORIGIN=http://localhost:<bff port>` (re-derive with kind=`bff` from the same deterministic helper — sibling BFF is TASK-007 in this capability; do not invent the value).
   - `platform.compose.yml` — opt-in stand-in: creates the external network only (frontend needs no infra).
   - `README.md` — short usage note.

2. **`frontend/deployment/dev/k8s/{base,overlay/dev}/`** — kustomize derived via `tech` from `runtime/static_hosting` (frontend hosting), `runtime/deploy` (namespace + PodSecurity + Quotas), `runtime/api_ingress` (Ingress with URL contract `https://k8s.<base>/{env}/BNK.RLVR.CAP.CHN.001.DSH/`), `identity/secrets` + `identity/workload`. Base = nginx Deployment + Service; overlay/dev = namespace + Ingress.

3. **`frontend/deployment/dev/terraform/`** — banking-tech modules only, derived via `tech` (typically resolves to `runtime/static_hosting` → S3 + CloudFront). Inputs limited to `project_name`, `environment="dev"`, `tenant`, `tags`. If any needed resource has no module, open the escape-hatch issue at `Banking-PapeeteConsulting/banking-tech` and record the URL.

4. **Append** to `/deployment/PORTS.md` the row `BNK.RLVR.CAP.CHN.001.DSH:frontend → <port>` for audit.

## Scope guardrails — read carefully

This is **first-time deployment scaffolding** on an existing component. Nothing
about the static files changes:

- ❌ DO NOT modify `index.html`, `styles.css`, `app.js`, `api.js`, `i18n.js`, `stub-data.js`, `dev.html`, `README.md` (the existing component README, distinct from the deployment one).
- ❌ DO NOT alter the dignity rule, consent gate, French vocabulary, stub-data canonical block, branch badge, or testability hooks.
- ✅ ONLY create files under `frontend/deployment/`.
- ✅ `api.js` may need an in-the-clear adjustment to read the BFF origin from a runtime-injected value (e.g. nginx-template or `<meta>` tag) rather than a hardcoded port — but only if doing so requires no behavioural change. If unsure, leave `api.js` alone and have nginx serve the same files verbatim; the BFF discovery problem stays solved by the existing dev story.

## Definition of Done

- [ ] `frontend/deployment/local/` contains `Dockerfile`, `nginx.conf`, `docker-compose.yml`, `.env`, `platform.compose.yml`, `README.md`.
- [ ] `frontend/deployment/dev/k8s/{base,overlay/dev}/` exist with kustomize manifests derived via `tech`.
- [ ] `frontend/deployment/dev/terraform/` exists with a banking-tech-modules-only root referencing `runtime/static_hosting` (escape-hatch GH issue URL recorded in its `README.md` if any resource has no module).
- [ ] `/deployment/PORTS.md` records the deterministic `BNK.RLVR.CAP.CHN.001.DSH:frontend → <port>` row.
- [ ] `docker compose -f frontend/deployment/local/docker-compose.yml up -d --build` succeeds; `GET http://localhost:<COMPONENT_PORT>/` returns the existing `index.html` (200, HTML, content unchanged from the static source).
- [ ] Stage 5 test agent (`test-app`) passes against the new paths — Playwright reaches the frontend on the deterministic port; the sibling BFF (TASK-007) is reachable on its deterministic port if it has been migrated.

## Acceptance Criteria (Business)

- **No behavioural change to the frontend itself.** The dignity rule, consent gate, French vocabulary, scenario coverage, and stub-data fallback remain bit-identical to the pre-migration files. Only a new image-based serving substrate is added; the legacy `python -m http.server` dev story is superseded but not enforced (devs may still serve the static files directly during local edits).

## Dependencies

- None hard. Sibling BFF migration is **TASK-007** in this capability; the two can run in either order. Coordinate with the **"one active task per capability"** invariant.

## Open Questions

- None.
