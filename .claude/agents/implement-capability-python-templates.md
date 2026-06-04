# Python Code Templates

Canonical layouts for the Python `implement-capability-python` agent.

> **Layout note:** the Dockerfile, `docker-compose.yml`, `.env`, optional
> `platform.compose.yml`, and `README.md` templates below all render to
> `sources/{capability-kebab}/backend/deployment/local/` — NOT to the
> component root. The Python settings module (`settings.py`) stays at its
> current location under `src/{namespace}_{capability_module}/infrastructure/settings.py`.

All placeholders: `{namespace}`, `{Namespace}`, `{capability_module}`,
`{CapabilityName}`, `{aggregate_module}`, `{AggregateName}`,
`{capability-kebab}`, `{capability_snake}`, `{COMPONENT_PORT}`,
`{branch}`, `{channel}`, `{exchange}`,
`{capability_id_lower_dotted}` (e.g. `cap.sup.002.ben`).

The templates below assume **MongoDB + motor** as the default
persistence. Switch to PostgreSQL + psycopg v3 (async) when the
TECH-TACT ADR tags `postgresql` — the swap-in is documented at the end
of this file.

---

## pyproject.toml

```toml
[project]
name = "{namespace}-{capability-kebab}"
version = "0.1.0"
description = "{CapabilityName} — Reliever capability"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "pydantic>=2.9",
  "pydantic-settings>=2.6",
  "motor>=3.6",                 # swap for psycopg[binary,pool]>=3.2 if Postgres
  "aio-pika>=9.4",
  "structlog>=24.4",
  "opentelemetry-distro>=0.49b0",
  "opentelemetry-exporter-otlp>=1.28",
  "jsonschema>=4.23",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "pytest-cov>=5.0",
  "httpx>=0.28",
  "ruff>=0.7",
  "mypy>=1.13",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{namespace}_{capability_module}"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## Dockerfile

```dockerfile
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ ./src/
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY config/ /app/config/
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=6 \
  CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["uvicorn", "{namespace}_{capability_module}.presentation.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## docker-compose.yml  (component-only — joins the external `reliever-platform` network)

The component compose ships **only** the component service. RabbitMQ and the
per-L2 database are provided by the platform (or by the stand-in
`platform.compose.yml` below) on the external `reliever-platform` Docker
network — services are reached by name (`rabbitmq`, `postgres`, `mongo`).

```yaml
services:
  {capability-kebab}-api:
    image: {capability-kebab}-api:dev
    build: .
    env_file: .env
    networks: [reliever-platform]
    ports: ["${COMPONENT_PORT}:8000"]
    healthcheck:
      test: ["CMD","curl","-fsS","http://localhost:8000/health"]
      interval: 10s
      retries: 6
networks:
  reliever-platform: { external: true }
```

---

## .env  (deployment/local/.env)

```
COMPONENT_PORT={COMPONENT_PORT}
RELIEVER_HTTP_HOST=0.0.0.0
RELIEVER_HTTP_PORT=8000
RELIEVER_AMQP_URL=amqp://admin:password@rabbitmq:5672/
# Use one of the two below depending on the TECH-TACT tag:
RELIEVER_PG_DSN=postgresql://reliever:reliever@postgres:5432/{capability_snake}
# RELIEVER_MONGO_URL=mongodb://mongo:27017/{capability_snake}
```

---

## platform.compose.yml  (OPTIONAL stand-in — NOT the real platform)

Sibling of `docker-compose.yml` under `deployment/local/`. Opt-in convenience
for devs without the real platform and for the test agents. It creates the
external `reliever-platform` network plus RabbitMQ + the per-L2 DB on standard
host ports. Pick the DB service that matches the TECH-TACT ADR tag
(`postgresql` / `mongodb`) — keep one, drop the other.

```yaml
# Stand-in platform for local dev / tests — NOT the real platform.
# Pick the DB service that matches the TECH-TACT ADR tag (postgresql / mongodb).
services:
  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    ports: ["5672:5672", "15672:15672"]
    environment: { RABBITMQ_DEFAULT_USER: admin, RABBITMQ_DEFAULT_PASS: password }
    healthcheck: { test: ["CMD","rabbitmq-diagnostics","-q","ping"], interval: 10s, retries: 6 }
  # postgresql variant
  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_USER: reliever
      POSTGRES_PASSWORD: reliever
      POSTGRES_DB: {capability_snake}
    healthcheck: { test: ["CMD-SHELL","pg_isready -U reliever -d {capability_snake}"], interval: 5s, retries: 10 }
  # mongodb variant (keep one of postgres / mongo, not both)
  # mongo:
  #   image: mongo:7
  #   ports: ["27017:27017"]
  #   healthcheck: { test: ["CMD-SHELL","mongosh --quiet --eval 'db.runCommand({ping:1}).ok' | grep 1"], interval: 10s, retries: 6 }
networks:
  default:
    name: reliever-platform
    external: true
```

---

## config/cold.toml

```toml
# Immutable per-deploy configuration.
[service]
name = "{namespace}-{capability-kebab}"
version = "0.1.0"
capability_id = "{CAP_ID}"
capability_zone = "{ZONE}"

[observability]
otel_service_name = "{namespace}-{capability-kebab}"
otel_resource_attributes = "capability.id={CAP_ID},capability.zone={ZONE}"

[bus]
exchange = "{exchange}"
channel_slug = "{channel}"
```

## config/hot.toml

```toml
# Runtime-tunable configuration.
[http]
host = "0.0.0.0"
port = 8000

[database]
url = "mongodb://mongo:27017/{capability_module}"
database_name = "{capability_module}"

[bus]
amqp_url = "amqp://admin:password@rabbitmq:5672/"

[logging]
level = "INFO"
```

---

## src/{namespace}_{capability_module}/__init__.py

```python
"""{CapabilityName} capability — Reliever programme.

This package implements the {CAP_ID} capability following hexagonal
architecture: domain (pure), application (use cases), infrastructure
(adapters), presentation (FastAPI + aio-pika), contracts (DTOs).
"""

__version__ = "0.1.0"
```

---

## src/{namespace}_{capability_module}/domain/errors.py

```python
"""Domain error codes.

Mirrors the `.model.aggregates` invariants from `kpack process <CAP_ID>`.
"""
from enum import StrEnum


class DomainErrorCode(StrEnum):
    AGGREGATE_NOT_FOUND = "AGGREGATE_NOT_FOUND"
    INVARIANT_VIOLATED = "INVARIANT_VIOLATED"
    INVALID_TRANSITION = "INVALID_TRANSITION"


class DomainError(Exception):
    def __init__(self, code: DomainErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
```

---

## src/{namespace}_{capability_module}/domain/{aggregate_module}/aggregate.py

```python
"""{AggregateName} aggregate root.

Encapsulates {AggregateName} state and invariants. Pure domain code —
no I/O, no framework dependencies. Mirrors AGG.* identifiers from
`.model.aggregates` (kpack process <CAP_ID>).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from ..errors import DomainError, DomainErrorCode


@dataclass(slots=True)
class {AggregateName}:
    id: UUID
    created_at: datetime
    updated_at: datetime
    # Add fields per the FUNC ADR's carried business object.

    @classmethod
    def create(cls, id: UUID) -> "{AggregateName}":
        now = datetime.now(UTC)
        return cls(id=id, created_at=now, updated_at=now)

    def assert_invariants(self) -> None:
        # Validate every business rule from .model.aggregates (kpack process <CAP_ID>).
        if self.created_at > self.updated_at:
            raise DomainError(
                DomainErrorCode.INVARIANT_VIOLATED,
                "created_at must precede updated_at",
            )
```

---

## src/{namespace}_{capability_module}/domain/{aggregate_module}/dto.py

```python
"""{AggregateName} DTO — pydantic v2 model for wire / persistence boundary."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class {AggregateName}Dto(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
```

---

## src/{namespace}_{capability_module}/domain/{aggregate_module}/repository.py

```python
"""Repository Protocol for {AggregateName} — abstract port (DDD)."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .aggregate import {AggregateName}


class Repository{AggregateName}(Protocol):
    async def get(self, id: UUID) -> {AggregateName} | None: ...
    async def save(self, aggregate: {AggregateName}) -> None: ...
```

---

## src/{namespace}_{capability_module}/domain/{aggregate_module}/factory.py

```python
"""Factory for {AggregateName} — encapsulates construction invariants."""
from __future__ import annotations

from uuid import UUID, uuid4

from .aggregate import {AggregateName}


class {AggregateName}Factory:
    def create(self, id: UUID | None = None) -> {AggregateName}:
        return {AggregateName}.create(id=id or uuid4())
```

---

## src/{namespace}_{capability_module}/application/{aggregate_module}/ports.py

```python
"""Application service Protocols — one per command."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from ...contracts.commands import Create{AggregateName}Command


class Create{AggregateName}Service(Protocol):
    async def execute(self, command: Create{AggregateName}Command) -> UUID: ...
```

---

## src/{namespace}_{capability_module}/application/{aggregate_module}/services.py

```python
"""Application services for {AggregateName} — orchestrate domain + repository."""
from __future__ import annotations

from uuid import UUID

import structlog

from ...contracts.commands import Create{AggregateName}Command
from ...contracts.events import {AggregateName}Created
from ...domain.{aggregate_module}.factory import {AggregateName}Factory
from ...domain.{aggregate_module}.repository import Repository{AggregateName}

log = structlog.get_logger(__name__)


class Create{AggregateName}ServiceImpl:
    def __init__(
        self,
        repository: Repository{AggregateName},
        factory: {AggregateName}Factory,
        publish_event,  # Callable[[BaseModel], Awaitable[None]]
    ) -> None:
        self._repository = repository
        self._factory = factory
        self._publish = publish_event

    async def execute(self, command: Create{AggregateName}Command) -> UUID:
        log.info("create_{aggregate_module}.start", command_id=command.command_id)
        aggregate = self._factory.create()
        aggregate.assert_invariants()
        await self._repository.save(aggregate)
        await self._publish(
            {AggregateName}Created(
                aggregate_id=aggregate.id,
                created_at=aggregate.created_at,
            )
        )
        log.info("create_{aggregate_module}.done", aggregate_id=str(aggregate.id))
        return aggregate.id
```

---

## src/{namespace}_{capability_module}/infrastructure/persistence/{aggregate_module}_repository.py  (motor)

```python
"""Motor (async MongoDB) repository for {AggregateName}."""
from __future__ import annotations

from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from ...domain.{aggregate_module}.aggregate import {AggregateName}
from ...domain.{aggregate_module}.dto import {AggregateName}Dto


class {AggregateName}MongoRepository:
    COLLECTION = "{AggregateName}Dto"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db[self.COLLECTION]

    async def get(self, id: UUID) -> {AggregateName} | None:
        raw = await self._collection.find_one({"id": str(id)})
        if raw is None:
            return None
        dto = {AggregateName}Dto.model_validate(raw)
        return {AggregateName}(
            id=dto.id, created_at=dto.created_at, updated_at=dto.updated_at
        )

    async def save(self, aggregate: {AggregateName}) -> None:
        dto = {AggregateName}Dto(
            id=aggregate.id,
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )
        await self._collection.replace_one(
            {"id": str(dto.id)}, dto.model_dump(mode="json"), upsert=True
        )
```

---

## src/{namespace}_{capability_module}/contracts/commands.py

```python
"""Command DTOs — mirror .model.commands CMD.* shapes (kpack process <CAP_ID>)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Create{AggregateName}Command(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    command_id: UUID = Field(..., description="Idempotency key for this command")
    issued_at: datetime
    # Add fields per .model.commands (kpack process <CAP_ID>).
```

---

## src/{namespace}_{capability_module}/contracts/events.py

```python
"""Event DTOs — mirror .model.bus RVT.* (kpack process <CAP_ID>) and the FUNC ADR's EVT.*."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class {AggregateName}Created(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    aggregate_id: UUID
    created_at: datetime
```

---

## src/{namespace}_{capability_module}/presentation/settings.py

```python
"""Application settings — loaded from env + config/*.toml via pydantic-settings."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RELIEVER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    capability_id: str = "{CAP_ID}"
    capability_zone: str = "{ZONE}"
    http_host: str = "0.0.0.0"
    http_port: int = 8000
    database_url: str = "mongodb://mongo:27017/{capability_module}"
    database_name: str = "{capability_module}"
    amqp_url: str = "amqp://admin:password@rabbitmq:5672/"
    bus_exchange: str = "{exchange}"
    bus_channel_slug: str = "{channel}"
    log_level: str = "INFO"
    otel_endpoint: str | None = Field(default=None, description="OTLP exporter endpoint")


def get_settings() -> AppSettings:
    return AppSettings()
```

---

## src/{namespace}_{capability_module}/presentation/lifespan.py

```python
"""FastAPI lifespan — connects DB and bus on startup, releases on shutdown."""
from __future__ import annotations

import contextlib
from typing import AsyncIterator

import aio_pika
import structlog
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from .settings import get_settings

log = structlog.get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    log.info("lifespan.startup", capability=settings.capability_id)

    mongo_client = AsyncIOMotorClient(settings.database_url)
    app.state.db = mongo_client[settings.database_name]

    amqp_conn = await aio_pika.connect_robust(settings.amqp_url)
    amqp_channel = await amqp_conn.channel()
    app.state.exchange = await amqp_channel.declare_exchange(
        settings.bus_exchange, aio_pika.ExchangeType.TOPIC, durable=True
    )

    try:
        yield
    finally:
        log.info("lifespan.shutdown")
        await amqp_conn.close()
        mongo_client.close()
```

---

## src/{namespace}_{capability_module}/presentation/app.py

```python
"""FastAPI factory — mounts routers, health endpoint, OTel instrumentation."""
from __future__ import annotations

from fastapi import FastAPI

from .lifespan import lifespan
from .routers import {aggregate_module}_cmd, {aggregate_module}_read


def create_app() -> FastAPI:
    app = FastAPI(
        title="{CapabilityName}",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router({aggregate_module}_cmd.router)
    app.include_router({aggregate_module}_read.router)
    return app


app = create_app()
```

---

## src/{namespace}_{capability_module}/presentation/routers/{aggregate_module}_cmd.py

```python
"""Command routes for {AggregateName} — one POST per command in commands.yaml."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request

from ...application.{aggregate_module}.services import Create{AggregateName}ServiceImpl
from ...contracts.commands import Create{AggregateName}Command
from ...domain.{aggregate_module}.factory import {AggregateName}Factory
from ...infrastructure.persistence.{aggregate_module}_repository import (
    {AggregateName}MongoRepository,
)

router = APIRouter(prefix="/{capability-kebab}", tags=["{capability-kebab}"])


async def _service(request: Request) -> Create{AggregateName}ServiceImpl:
    repo = {AggregateName}MongoRepository(request.app.state.db)
    factory = {AggregateName}Factory()

    async def publish(event) -> None:
        import aio_pika
        await request.app.state.exchange.publish(
            aio_pika.Message(body=event.model_dump_json().encode()),
            routing_key="{AggregateName}.Created",
        )

    return Create{AggregateName}ServiceImpl(repo, factory, publish)


@router.post("/{aggregate_module}", status_code=201)
async def create_{aggregate_module}(
    command: Create{AggregateName}Command,
    svc: Create{AggregateName}ServiceImpl = Depends(_service),
) -> dict[str, str]:
    aggregate_id: UUID = await svc.execute(command)
    return {"id": str(aggregate_id)}
```

---

## src/{namespace}_{capability_module}/presentation/routers/{aggregate_module}_read.py

```python
"""Read routes for {AggregateName} — mirror .model['read-models'] (kpack process <CAP_ID>)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from ...infrastructure.persistence.{aggregate_module}_repository import (
    {AggregateName}MongoRepository,
)

router = APIRouter(prefix="/{capability-kebab}", tags=["{capability-kebab}-read"])


@router.get("/{aggregate_module}/{{id}}")
async def get_{aggregate_module}(id: UUID, request: Request) -> dict:
    repo = {AggregateName}MongoRepository(request.app.state.db)
    aggregate = await repo.get(id)
    if aggregate is None:
        raise HTTPException(status_code=404, detail="not found")
    return {
        "id": str(aggregate.id),
        "created_at": aggregate.created_at.isoformat(),
        "updated_at": aggregate.updated_at.isoformat(),
    }
```

---

## src/{namespace}_{capability_module}/presentation/messaging/consumer.py

```python
"""aio-pika consumer — subscribes to upstream RVT.* events declared in .model.bus (kpack process <CAP_ID>).

Only materialise this module when consumed_events[] | select(.layer=="resource") is non-empty.
"""
from __future__ import annotations

import aio_pika
import structlog

log = structlog.get_logger(__name__)


async def bind_subscriptions(channel: aio_pika.abc.AbstractChannel, queue_name: str,
                              source_exchange: str, routing_keys: list[str]) -> aio_pika.abc.AbstractQueue:
    exchange = await channel.declare_exchange(source_exchange, aio_pika.ExchangeType.TOPIC, durable=True)
    queue = await channel.declare_queue(queue_name, durable=True)
    for rk in routing_keys:
        await queue.bind(exchange, routing_key=rk)
    log.info("consumer.bound", queue=queue_name, source=source_exchange, keys=routing_keys)
    return queue
```

---

## tests/test_health.py

```python
"""Smoke test — service starts and /health returns 200."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from {namespace}_{capability_module}.presentation.app import create_app


@pytest.mark.asyncio
async def test_health_returns_ok() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

---

## PostgreSQL swap-in (TECH-TACT ADR tags `postgresql`)

Apply these substitutions on top of the MongoDB templates above.

**pyproject.toml** — replace `motor>=3.6` with:

```toml
  "psycopg[binary,pool]>=3.2",
```

**docker-compose.yml** — no change. The component compose ships only the
component service and joins the external `reliever-platform` network; the
database is provided by the platform (or by the `platform.compose.yml`
stand-in) and resolved by service name (`postgres`).

**platform.compose.yml** — keep the `postgres` service block (already
templated above) and **delete the commented `mongo` variant**.

**.env** — switch to the Postgres DSN line, comment out the Mongo URL:

```
RELIEVER_PG_DSN=postgresql://reliever:reliever@postgres:5432/{capability_snake}
# RELIEVER_MONGO_URL=mongodb://mongo:27017/{capability_snake}
```

**hot.toml** — replace `[database]` block:

```toml
[database]
url = "postgresql://reliever:reliever@postgres:5432/{capability_snake}"
```

**settings.py** — `database_url` default changes to the Postgres DSN above.

**infrastructure/persistence/{aggregate_module}_repository.py** —
replace the motor implementation with a psycopg v3 async one:

```python
"""psycopg (async) repository for {AggregateName}."""
from __future__ import annotations

from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from ...domain.{aggregate_module}.aggregate import {AggregateName}


class {AggregateName}PostgresRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def get(self, id: UUID) -> {AggregateName} | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, created_at, updated_at FROM {aggregate_module} WHERE id = %s",
                (str(id),),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return {AggregateName}(id=row[0], created_at=row[1], updated_at=row[2])

    async def save(self, aggregate: {AggregateName}) -> None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO {aggregate_module} (id, created_at, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                  SET updated_at = EXCLUDED.updated_at
                """,
                (str(aggregate.id), aggregate.created_at, aggregate.updated_at),
            )
            await conn.commit()
```

**lifespan.py** — replace the motor section with:

```python
from psycopg_pool import AsyncConnectionPool

pool = AsyncConnectionPool(settings.database_url, open=False)
await pool.open()
app.state.db_pool = pool

# Schema bootstrap — replace with Alembic / migrations in production.
async with pool.connection() as conn, conn.cursor() as cur:
    await cur.execute(
        "CREATE TABLE IF NOT EXISTS {aggregate_module} ("
        "id UUID PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL)"
    )
    await conn.commit()
```

The repository constructor signature changes from
`AsyncIOMotorDatabase` to `AsyncConnectionPool`; update the
router dependency accordingly.
