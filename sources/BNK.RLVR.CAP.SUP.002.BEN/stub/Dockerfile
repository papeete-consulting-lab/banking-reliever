FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project 2>/dev/null || uv sync --no-dev --no-install-project
COPY src/ ./src/
COPY fixtures/ ./fixtures/
COPY config/ ./config/
RUN uv sync --no-dev

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/fixtures /app/fixtures
COPY --from=builder /app/config /app/config
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
EXPOSE 54679
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:54679/health').read()" || exit 1
CMD ["uvicorn", "reliever_beneficiary_identity_anchor_stub.app:app", "--host", "0.0.0.0", "--port", "54679"]
