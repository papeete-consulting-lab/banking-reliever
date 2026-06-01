# Universal build for the BNK.RLVR.CAP.BSP.001.SCO contract+stub (Mode B, Python).
#
# Per CLAUDE.md § "Deployment contract (local + dev)": ONE Dockerfile is the
# universal build — the same image is consumed locally via docker-compose AND
# pulled from ECR (delivery/registry) for dev/staging/prod. No per-environment
# Dockerfiles.
#
# Owner-capability: BNK.RLVR.CAP.BSP.001.SCO (Behavioural Scoring)
# Stack          : Python 3.12 + aio-pika + jsonschema (TECH-TACT tags python/fastapi)
# Kind           : api (contract+stub publisher; no DB, no Kafka)
# Build invariant: identical hash from any worktree given the same src/ tree.

FROM python:3.12-slim AS base

# Reproducible-friendly: no .pyc, unbuffered stdio, no pip cache, no version check.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Minimal runtime tooling. curl is kept for container-level diagnostics; the
# stub itself has no HTTP server (pure RabbitMQ publisher), so the
# docker-compose healthcheck uses a Python liveness probe — see compose file.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Drop privileges — the stub runs unprivileged in production too.
RUN groupadd --gid 10001 stub \
 && useradd  --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin stub

WORKDIR /app

# Dependency layer (cache-friendly). requirements.txt mirrors pyproject.toml.
COPY --chown=stub:stub requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Application sources + package metadata.
COPY --chown=stub:stub pyproject.toml /app/pyproject.toml
COPY --chown=stub:stub src/ /app/src/

# Install the package itself (exposes the bsp-sco-stub entry point and ships
# the vendored RVT.*/CMD.* schema snapshot inside the wheel — see
# [tool.setuptools.package-data] in pyproject.toml).
RUN pip install --no-cache-dir /app

USER stub

# COMPONENT_PORT is informational for this stub — the publisher has no HTTP
# server (pure RabbitMQ producer). Kept as an env var so the .env contract is
# uniform across components and the deterministic port is documented end-to-end.
EXPOSE 23074

# Default runtime knobs (overridable via env). STUB_ACTIVE stays false here —
# the compose .env flips it to true for the local-test loop.
ENV STUB_LOG_LEVEL=INFO \
    STUB_ACTIVE=false

ENTRYPOINT ["python", "-m", "bsp_sco_stub"]
