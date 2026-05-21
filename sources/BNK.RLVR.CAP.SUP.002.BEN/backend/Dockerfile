# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.12

# ─── Builder ──────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build tooling + project sources, then wheel-install into a clean
# /install directory so the runtime image stays slim.
COPY pyproject.toml ./
COPY src ./src

RUN pip install --upgrade pip build && \
    pip install --prefix=/install .

# ─── Runtime ──────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RELIEVER_HTTP_HOST=0.0.0.0 \
    RELIEVER_HTTP_PORT=8000

WORKDIR /app

# Copy the installed packages from the builder.
COPY --from=builder /install /usr/local

# Copy migrations + process-layer schemas. The container must be able to
# load the canonical JSON Schemas — they are mounted from /process inside
# the container.
COPY migrations ./migrations

# The schemas are mounted from the repo at runtime (read-only) so they
# always reflect the merged process/ contract. Default container path:
ENV RELIEVER_PROCESS_SCHEMAS_DIR=/process/BNK.RLVR.CAP.SUP.002.BEN/schemas
ENV RELIEVER_MIGRATIONS_DIR=/app/migrations

EXPOSE 8000

CMD ["uvicorn", "reliever_beneficiary_anchor.presentation.app:app", \
     "--host", "0.0.0.0", "--port", "8000"]
