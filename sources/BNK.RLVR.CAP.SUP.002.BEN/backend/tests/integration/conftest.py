"""Integration-test fixtures — require docker compose up first.

We deliberately do NOT spawn testcontainers here so the tests are runnable
both locally (against ``docker compose up``) and in CI (against a job-local
compose). The DSN / AMQP URL default to the docker-compose host bindings.
"""

from __future__ import annotations

import asyncio
import os
import socket
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio

# Allow opt-in skipping when docker compose isn't up.
pytestmark = pytest.mark.integration


def _broker_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_infra():
    """Skip the integration module gracefully if the infra isn't reachable."""
    pg_host = os.environ.get("RELIEVER_TEST_PG_HOST", "localhost")
    pg_port = int(os.environ.get("RELIEVER_TEST_PG_PORT", "9043"))
    mq_host = os.environ.get("RELIEVER_TEST_AMQP_HOST", "localhost")
    mq_port = int(os.environ.get("RELIEVER_TEST_AMQP_PORT", "9054"))
    if not _broker_reachable(pg_host, pg_port):
        pytest.skip(f"PostgreSQL not reachable at {pg_host}:{pg_port}")
    if not _broker_reachable(mq_host, mq_port):
        pytest.skip(f"RabbitMQ not reachable at {mq_host}:{mq_port}")


@pytest.fixture(scope="session")
def pg_dsn() -> str:
    return os.environ.get(
        "RELIEVER_TEST_PG_DSN",
        "postgresql://reliever:reliever@localhost:9043/beneficiary_anchor",
    )


@pytest.fixture(scope="session")
def amqp_url() -> str:
    return os.environ.get(
        "RELIEVER_TEST_AMQP_URL",
        "amqp://admin:password@localhost:9054/",
    )


@pytest_asyncio.fixture
async def app_settings(pg_dsn, amqp_url, schemas_dir, migrations_dir):
    """Per-test settings with a unique projection queue + isolated test DB schema
    semantics (we rely on a clean test DB or on truncation between tests)."""
    from reliever_beneficiary_anchor.presentation.settings import Settings

    return Settings(
        pg_dsn=pg_dsn,
        amqp_url=amqp_url,
        projection_queue=f"sup.002.ben.anchor-directory.test-{uuid.uuid4().hex[:8]}",
        process_schemas_dir=schemas_dir,
        migrations_dir=migrations_dir,
        run_migrations_on_startup=True,
    )


@pytest_asyncio.fixture
async def reset_db(pg_dsn):
    """Truncate all test tables before the test."""
    import psycopg

    async with await psycopg.AsyncConnection.connect(pg_dsn) as conn:
        async with conn.cursor() as cur:
            # Create the tables first (migrations are idempotent; they no-op
            # if the schema already exists).
            migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
            for path in sorted(migrations_dir.glob("*.sql")):
                await cur.execute(path.read_text())  # type: ignore[arg-type]
            await cur.execute(
                "TRUNCATE anchor, anchor_directory, outbox, idempotency_keys RESTART IDENTITY"
            )
        await conn.commit()
    yield
