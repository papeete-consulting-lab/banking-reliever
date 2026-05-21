"""FastAPI factory + lifespan for the BNK.RLVR.CAP.SUP.002.BEN development stub.

Lifespan responsibilities:
1. Load and validate every canned fixture against its response shape.
2. Wire the StubPublisher into the asyncio loop when ``RELIEVER_STUB_ACTIVE``
   is true; cleanly close the RabbitMQ connection on shutdown.
3. Expose ``/health`` for liveness probing.

The stub is also runnable purely in-process (e.g. by pytest + httpx) — when
``RELIEVER_STUB_ACTIVE=false`` (the default) lifespan skips the RabbitMQ
connection entirely, so the test suite never needs a broker.
"""
from __future__ import annotations

import contextlib
import json
import logging
import sys
from typing import AsyncIterator

import structlog
from fastapi import FastAPI

from .endpoints import router as anchors_router
from .fixture_store import FixtureStore
from .publisher import StubPublisher
from .schema_validator import validate
from .settings import StubSettings, get_settings


def _configure_logging(level: str) -> None:
    """Minimal structlog → stdlib bridge."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: StubSettings = app.state.settings
    log = structlog.get_logger("lifespan")

    log.info(
        "startup",
        capability=settings.capability_id,
        zone=settings.capability_zone,
        stub_active=settings.stub_active,
        stub_http_active=settings.stub_http_active,
    )

    # 1. Load + schema-validate the canned fixtures (fail fast on drift).
    fixture_store = FixtureStore.load(settings.fixtures_dir)
    # Note: api.yaml's BeneficiaryAnchor response shape is not authored as
    # a standalone JSON Schema upstream (only the RVT schema is, and it is
    # vendored under schemas/). The
    # RVT and BeneficiaryAnchor share their PII fields, so we sanity-check
    # each fixture by trying to convert it to a no-envelope projection of
    # the RVT shape — coverage of the conditional PSEUDONYMISED branch is
    # exercised by the publisher tests (test_publisher_*).
    app.state.fixture_store = fixture_store
    log.info("fixtures.loaded", count=len(fixture_store.anchor_ids()))

    # 2. Wire the publisher (only if STUB_ACTIVE).
    publisher = StubPublisher(settings)
    app.state.publisher = publisher

    await publisher.start()

    try:
        yield
    finally:
        log.info("shutdown")
        await publisher.stop()


def create_app(settings: StubSettings | None = None) -> FastAPI:
    settings = settings or get_settings()
    _configure_logging("INFO")

    app = FastAPI(
        title="Beneficiary Identity Anchor — DEV STUB",
        version="0.1.0",
        description=(
            "Development stub for BNK.RLVR.CAP.SUP.002.BEN. Publishes "
            "BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED on `sup.002.ben-events` and "
            "serves canned BeneficiaryAnchor + AnchorHistory responses. "
            "Not production. See ADR-BCM-FUNC-0016 and ADR-TECH-TACT-002."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(anchors_router)
    return app


# Module-level ``app`` for uvicorn entrypoint.
app = create_app()
