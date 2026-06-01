# Deployment contract — universal build (CLAUDE.md § "Deployment contract").
#
# Owner-capability : BNK.RLVR.CAP.SUP.002.BEN (Beneficiary Identity Anchor)
# Component        : stub (Mode-B contract+stub — FastAPI HTTP + aio-pika
#                    publisher of synthetic RVT events; serves canned
#                    fixtures for the GET query half)
# Stack            : Python 3.12+ / FastAPI / aio-pika
#                    (TECH-TACT tags include: python, fastapi, …)
# Kind             : api  (the stub is consumed by downstream stubs as the
#                    BNK.RLVR.CAP.SUP.002.BEN HTTP+bus surface)
# Build artefact   : ONE Dockerfile — same image is consumed locally via
#                    docker-compose AND pulled from ECR for dev. No
#                    per-environment Dockerfiles.
# Reproducibility  : `uv` resolves against the committed `uv.lock`; the
#                    image is bit-stable for any worktree on the same source.
#
# Migration note (TASK-008): semantically equivalent to the legacy root-level
# stub/Dockerfile this file replaces. The container's internal port is
# normalised to 8000 (uvicorn default) so the only host port that varies is
# the deterministic COMPONENT_PORT in docker-compose.yml + .env (no more
# hardcoded 54679 anywhere). Same multi-stage layout, same base image, same
# uvicorn entrypoint, same fixtures + config copy.
#
# Filesystem layout preserved at /app — the stub's `settings.py` resolves
# `stub_root` and `fixtures_dir` via `__file__`-relative parents (see
# src/reliever_beneficiary_identity_anchor_stub/settings.py); we keep
# `WORKDIR /app` + `/app/src/<pkg>/…` so those relative paths resolve
# identically inside the container and on a developer laptop.

# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.12

# ─── Builder ──────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install uv (frozen-lock-aware installer) into the builder stage only.
RUN pip install --upgrade pip "uv>=0.4,<0.5"

# Layer 1 — dependency manifest + lockfile.
# Copying these BEFORE the source tree lets Docker cache the
# `uv sync --frozen --no-install-project` step across source-only edits.
COPY pyproject.toml uv.lock ./

# Resolve dependencies (skip the project itself — fixtures aren't here yet).
RUN uv sync --frozen --no-dev --no-install-project 2>/dev/null \
 || uv sync --no-dev --no-install-project

# Layer 2 — application sources + canned fixtures + TOML config.
COPY src      ./src
COPY fixtures ./fixtures
COPY config   ./config

# Now install the project itself on top of the locked deps. The package's
# __file__-relative path resolution (settings.py reads
# `_STUB_ROOT = __file__.parents[2]`) means we want the venv → src/ links
# preserved, so we install in regular (NOT --no-editable) mode here.
RUN uv sync --frozen --no-dev 2>/dev/null \
 || uv sync --no-dev

# ─── Runtime ──────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}" \
    RELIEVER_HTTP_HOST=0.0.0.0 \
    RELIEVER_HTTP_PORT=8000

# Minimal runtime tooling. ca-certificates for TLS; wget for the compose-level
# healthcheck on /health (curl-free runtime keeps the image small).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates wget \
 && rm -rf /var/lib/apt/lists/*

# Drop privileges — the stub runs unprivileged in every environment.
RUN groupadd --gid 10001 reliever \
 && useradd  --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin reliever

WORKDIR /app

# Mirror the builder's /app tree so the package's __file__-relative paths
# (settings.py → stub_root / fixtures_dir) resolve identically:
#   /app/.venv/                 — locked deps + (editable) project install
#   /app/src/<pkg>/             — source tree the venv links to
#   /app/fixtures/              — canned anchors + history JSON
#   /app/config/                — stub.toml defaults
COPY --from=builder --chown=reliever:reliever /app/.venv    /app/.venv
COPY --from=builder --chown=reliever:reliever /app/src      /app/src
COPY --from=builder --chown=reliever:reliever /app/fixtures /app/fixtures
COPY --from=builder --chown=reliever:reliever /app/config   /app/config

USER reliever

# Deterministic component port (from /deployment/PORTS.md):
# COMPONENT_PORT = 20000 + ( sha256("BNK.RLVR.CAP.SUP.002.BEN:api:1")[:8] % 9000 )
#                = 21595  (salt=:1 — the salt-free 26835 is taken by
#                          the TASK-007 backend in the same capability)
# EXPOSE keeps cross-component uniformity at the container-internal port; the
# host binding to ${COMPONENT_PORT} lives in docker-compose.yml + .env.
EXPOSE 8000

# Container HTTP healthcheck (belt-and-braces for non-compose runners).
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=5 \
  CMD wget -qO- http://127.0.0.1:8000/health >/dev/null || exit 1

CMD ["uvicorn", "reliever_beneficiary_identity_anchor_stub.app:app", \
     "--host", "0.0.0.0", "--port", "8000"]
