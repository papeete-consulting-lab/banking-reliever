"""FastAPI dependency wiring — singletons stored on ``app.state``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool
    from aio_pika.abc import AbstractRobustConnection

    from ..application.handlers import (
        ArchiveAnchorHandler,
        GetAnchorHandler,
        MintAnchorHandler,
        RestoreAnchorHandler,
        UpdateAnchorHandler,
    )
    from ..application.ports import SchemaValidator
    from ..infrastructure.persistence.unit_of_work import PostgresUnitOfWorkFactory
    from ..infrastructure.messaging.publisher import AioPikaPublisher
    from ..infrastructure.messaging.outbox_relay import OutboxRelay
    from ..infrastructure.messaging.projection_consumer import ProjectionConsumer


@dataclass
class AppState:
    pg_pool: "AsyncConnectionPool"
    amqp_connection: "AbstractRobustConnection"
    publisher: "AioPikaPublisher"
    outbox_relay: "OutboxRelay | None"
    projection_consumer: "ProjectionConsumer | None"
    mint_validator: "SchemaValidator"
    update_validator: "SchemaValidator"
    archive_validator: "SchemaValidator"
    restore_validator: "SchemaValidator"
    rvt_validator: "SchemaValidator"
    uow_factory: "PostgresUnitOfWorkFactory"
    mint_handler: "MintAnchorHandler"
    update_handler: "UpdateAnchorHandler"
    archive_handler: "ArchiveAnchorHandler"
    restore_handler: "RestoreAnchorHandler"
    get_handler: "GetAnchorHandler"


def get_state(request: Request) -> AppState:
    return request.app.state.runtime  # type: ignore[no-any-return]
