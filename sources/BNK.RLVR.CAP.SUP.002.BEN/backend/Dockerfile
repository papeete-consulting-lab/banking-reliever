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

# The JSON Schemas the service validates against are VENDORED inside the
# package (src/reliever_beneficiary_anchor/infrastructure/schema_validation/
# schemas/) and ship in the installed wheel — the settings default resolves
# them package-locally, so no /process mount or env override is needed.
# (The process model itself lives upstream in reliever-knowledge — `rlv-knowledge
# process`.) Override RELIEVER_PROCESS_SCHEMAS_DIR only to point at a
# different snapshot.
COPY migrations ./migrations

ENV RELIEVER_MIGRATIONS_DIR=/app/migrations

EXPOSE 8000

CMD ["uvicorn", "reliever_beneficiary_anchor.presentation.app:app", \
     "--host", "0.0.0.0", "--port", "8000"]
