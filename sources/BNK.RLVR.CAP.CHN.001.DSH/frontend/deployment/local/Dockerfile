# syntax=docker/dockerfile:1.7
# Multi-stage build for the BNK.RLVR.CAP.CHN.001.DSH frontend
# (Beneficiary Dashboard — vanilla HTML5/CSS3/JS, served by nginx:alpine).
#
# Universal build artefact per the Deployment contract (CLAUDE.md §
# "Deployment contract (local + dev)"): the same image is used by
# `deployment/local/` and pulled by `deployment/dev/` from ECR
# (delivery/registry).
#
# Notes:
#   - Stage 1 stages the static bundle (vanilla HTML/CSS/JS — no toolchain).
#     Kept as a discrete stage so future bundling (esbuild, vite) can slot in
#     without changing the runtime contract.
#   - Stage 2 (runtime) is `nginx:alpine` serving `/usr/share/nginx/html` on
#     port 80. SPA-friendly routing (try_files) + sensible cache headers come
#     from `nginx.conf`.
#   - Build context is the REPO ROOT so the COPY path below resolves; mirrors
#     the BFF Dockerfile contract:
#       docker build \
#         -f sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/deployment/local/Dockerfile \
#         -t chn-001-dsh-frontend:dev .

# ── Stage 1 — stage the static bundle ──────────────────────────────────────
FROM alpine:3.20 AS bundle
WORKDIR /bundle

# Copy the static files that ship to the browser. The deployment/ subtree is
# explicitly excluded — only the bundle assets land in the image.
COPY sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/index.html      ./index.html
COPY sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/app.css         ./app.css
COPY sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/app.js          ./app.js
COPY sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/api.js          ./api.js
COPY sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/i18n.js         ./i18n.js
COPY sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/stub-data.js    ./stub-data.js
COPY sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/dev.html        ./dev.html

# ── Stage 2 — nginx runtime ────────────────────────────────────────────────
FROM nginx:alpine AS runtime

# nginx config (SPA-friendly try_files + cache headers + BFF reverse proxy).
COPY sources/BNK.RLVR.CAP.CHN.001.DSH/frontend/deployment/local/nginx.conf \
     /etc/nginx/conf.d/default.conf

# Static bundle.
COPY --from=bundle /bundle /usr/share/nginx/html

EXPOSE 80

LABEL capability_id="BNK.RLVR.CAP.CHN.001.DSH"
LABEL zone="chn"
LABEL kind="frontend"
LABEL deployable="reliever-chn"

# nginx ships its own /usr/sbin/nginx process — health is probed by docker
# compose / k8s on `GET /` (returns the static index.html with 200).
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
