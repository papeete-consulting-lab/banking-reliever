# Deployment contract — universal build (CLAUDE.md § "Deployment contract").
#
# Owner-capability : BNK.RLVR.CAP.SUP.002.BEN (Beneficiary Identity Anchor)
# Stack            : Python 3.12+ / FastAPI / psycopg / aio-pika
#                    (TECH-TACT tags: python, fastapi, postgresql, vault-transit,
#                    crypto-shredding, uuidv7, gdpr-erasure, …)
# Kind             : api (Mode-A full microservice — REST + bus publisher
#                    + outbox relay + projection consumer)
# Build artefact   : ONE Dockerfile is the universal image. The same image
#                    is consumed locally via docker-compose AND pulled from
#                    ECR (delivery/registry) for dev/staging/prod. No
#                    per-environment Dockerfiles.
# Reproducibility  : `uv` resolves against the committed `uv.lock`
#                    (tracked in commit 11c700e); the image is bit-stable
#                    for any worktree on the same source tree.
#
# Migration note (TASK-007): semantically equivalent to the legacy root-level
# backend/Dockerfile that this file replaces. Same multi-stage layout, same
# base image, same RELIEVER_HTTP_* env defaults, same EXPOSE/CMD pair. Only
# the dependency-install path is upgraded to `uv sync --frozen` so that
# `uv.lock` becomes the build's source of truth.

# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.12

# ─── Builder ──────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/install

WORKDIR /build

# Install uv (frozen-lock-aware installer) into the builder stage only.
# Pinned to a known-good 0.4.x; bump deliberately, not by accident.
RUN pip install --upgrade pip "uv>=0.4,<0.5"

# Layer 1 — dependency manifest + lockfile.
# Copying these BEFORE the source tree lets Docker cache the
# `uv sync --frozen --no-install-project` step across source-only edits.
COPY pyproject.toml uv.lock ./

# Layer 2 — application sources.
COPY src ./src

# Resolve and materialise all locked dependencies + the project into
# /install. `--frozen` refuses to drift from uv.lock — reproducibility.
# `--no-dev` keeps the runtime image free of pytest/ruff/etc.
# `--no-editable` performs a regular (non-editable) install so the
# package is fully materialised inside /install/lib/.../site-packages/,
# and the runtime stage (which does NOT carry /build/src) can import it.
RUN uv sync --frozen --no-dev --no-editable

# ─── Runtime ──────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/install/bin:${PATH}" \
    RELIEVER_HTTP_HOST=0.0.0.0 \
    RELIEVER_HTTP_PORT=8000

# Minimal runtime tooling. ca-certificates is the only required dep — the
# psycopg[binary] wheel ships its own libpq. wget is kept for the
# compose-level healthcheck on /health.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates wget \
 && rm -rf /var/lib/apt/lists/*

# Drop privileges — the microservice runs unprivileged in every environment.
RUN groupadd --gid 10001 reliever \
 && useradd  --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin reliever

WORKDIR /app

# Copy the materialised dependency tree + the installed package.
COPY --from=builder --chown=reliever:reliever /install /install

# Migrations are read at startup by the application — see
# RELIEVER_MIGRATIONS_DIR below. The JSON Schemas the service validates
# against are VENDORED inside the package (src/reliever_beneficiary_anchor/
# infrastructure/schema_validation/schemas/) and ship inside the installed
# wheel — the settings default resolves them package-locally. No /process
# mount and no env override is required (the process model lives upstream
# in reliever-knowledge — `rlv-knowledge process`).
COPY --chown=reliever:reliever migrations /app/migrations

ENV RELIEVER_MIGRATIONS_DIR=/app/migrations

USER reliever

# Deterministic component port (from /deployment/PORTS.md).
# COMPONENT_PORT = 20000 + ( sha256("BNK.RLVR.CAP.SUP.002.BEN:api")[:8] % 9000 )
#                = 26835
# EXPOSE keeps cross-component uniformity; the host binding lives in
# docker-compose.yml + .env.
EXPOSE 8000

# Container HTTP healthcheck (compose-managed) — see docker-compose.yml.
# This Dockerfile-level HEALTHCHECK is a belt-and-braces for non-compose
# runners (e.g. plain `docker run`). Uvicorn listens inside the container
# at 0.0.0.0:8000 regardless of the host port mapping.
HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=5 \
  CMD wget -qO- http://127.0.0.1:8000/health >/dev/null || exit 1

CMD ["uvicorn", "reliever_beneficiary_anchor.presentation.app:app", \
     "--host", "0.0.0.0", "--port", "8000"]
