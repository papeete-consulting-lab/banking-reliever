"""FastAPI application factory + lifespan wiring."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import aio_pika
import psycopg
import structlog
from fastapi import FastAPI
from psycopg_pool import AsyncConnectionPool

from ..application.handlers import (
    EXCHANGE_NAME,
    GetAnchorHandler,
    MintAnchorHandler,
    PseudonymiseAnchorHandler,
    ROUTING_KEY,
    UpdateAnchorHandler,
)
from ..infrastructure.messaging.outbox_relay import OutboxRelay
from ..infrastructure.messaging.projection_consumer import ProjectionConsumer
from ..infrastructure.messaging.publisher import AioPikaPublisher
from ..infrastructure.persistence.migrations import apply_migrations
from ..infrastructure.persistence.projection import (
    PostgresAnchorDirectoryReader,
    PostgresAnchorDirectoryWriter,
)
from ..infrastructure.persistence.unit_of_work import PostgresUnitOfWorkFactory
from ..infrastructure.schema_validation.loader import build_validators_bundle
from .dependencies import AppState
from .routers import install_exception_handlers, router as anchors_router
from .settings import Settings


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    _configure_logging()
    settings = settings or Settings()
    log = structlog.get_logger()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        log.info("startup.begin")

        # 1. Validators — fail-fast if a schema is missing/malformed.
        validators = build_validators_bundle(settings.process_schemas_dir)
        mint_validator = validators.mint
        update_validator = validators.update
        pseudonymise_validator = validators.pseudonymise
        rvt_validator = validators.rvt
        log.info("schemas.loaded", dir=str(settings.process_schemas_dir))

        # 2. Postgres pool.
        pool = AsyncConnectionPool(
            settings.pg_dsn,
            min_size=settings.pg_min_pool,
            max_size=settings.pg_max_pool,
            open=False,
        )
        await pool.open()
        await pool.wait()
        log.info("pg.pool_open", dsn=_redact_dsn(settings.pg_dsn))

        # 3. Migrations.
        if settings.run_migrations_on_startup:
            async with pool.connection() as conn:
                await conn.set_autocommit(True)
                await apply_migrations(conn, settings.migrations_dir)
            log.info("migrations.applied")

        # 4. RabbitMQ connection.
        amqp_conn = await aio_pika.connect_robust(settings.amqp_url)
        publisher = AioPikaPublisher(amqp_conn, settings.exchange_name)
        await publisher.ensure_exchange()

        # 5. Outbox relay.
        outbox_relay: OutboxRelay | None = None
        if settings.run_outbox_relay:
            outbox_relay = OutboxRelay(
                pool=pool,
                publisher=publisher,
                poll_interval_seconds=settings.outbox_poll_interval_seconds,
                batch_size=settings.outbox_batch_size,
            )
            await outbox_relay.start()

        # 6. Projection consumer.
        projection_consumer: ProjectionConsumer | None = None
        if settings.run_projection_consumer:
            writer = PostgresAnchorDirectoryWriter(pool)
            projection_consumer = ProjectionConsumer(
                connection=amqp_conn,
                exchange_name=settings.exchange_name,
                routing_key=settings.routing_key,
                queue_name=settings.projection_queue,
                writer=writer,
                validator=rvt_validator,
            )
            await projection_consumer.start()

        # 7. Application services.
        reader = PostgresAnchorDirectoryReader(pool)
        uow_factory = PostgresUnitOfWorkFactory(pool)
        mint_handler = MintAnchorHandler(
            uow_factory=uow_factory,
            rvt_validator=rvt_validator,
        )
        update_handler = UpdateAnchorHandler(
            uow_factory=uow_factory,
            rvt_validator=rvt_validator,
        )
        pseudonymise_handler = PseudonymiseAnchorHandler(
            uow_factory=uow_factory,
            rvt_validator=rvt_validator,
        )
        get_handler = GetAnchorHandler(reader=reader)

        app.state.runtime = AppState(
            pg_pool=pool,
            amqp_connection=amqp_conn,
            publisher=publisher,
            outbox_relay=outbox_relay,
            projection_consumer=projection_consumer,
            mint_validator=mint_validator,
            update_validator=update_validator,
            pseudonymise_validator=pseudonymise_validator,
            rvt_validator=rvt_validator,
            uow_factory=uow_factory,
            mint_handler=mint_handler,
            update_handler=update_handler,
            pseudonymise_handler=pseudonymise_handler,
            get_handler=get_handler,
        )
        log.info("startup.ready")

        try:
            yield
        finally:
            log.info("shutdown.begin")
            if outbox_relay is not None:
                await outbox_relay.stop()
            if projection_consumer is not None:
                await projection_consumer.stop()
            try:
                await amqp_conn.close()
            except Exception:  # noqa: BLE001
                log.exception("amqp.close_failed")
            await pool.close()
            log.info("shutdown.done")

    app = FastAPI(
        title="BNK.RLVR.CAP.SUP.002.BEN — Beneficiary Identity Anchor",
        version="0.1.0",
        description=(
            "The canonical anchor for beneficiary identity in Reliever "
            "(TASK-002 MINT + GET / TASK-003 UPDATE / TASK-005 GDPR Art. 17 "
            "pseudonymisation)."
        ),
        lifespan=lifespan,
    )
    app.include_router(anchors_router)
    install_exception_handlers(app)
    return app


def _redact_dsn(dsn: str) -> str:
    # Hide the password section for logs — best-effort.
    import re
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", dsn)


# uvicorn entry point: ``uvicorn reliever_beneficiary_anchor.presentation.app:app``
app = create_app()
