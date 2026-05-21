"""Ports — abstract interfaces for the infrastructure layer.

Defined as Protocols (and ABCs where stateful) so the infrastructure
implementations can be swapped (e.g. in-memory for unit tests).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ..domain.aggregate import IdentityAnchor


class UnitOfWork(ABC):
    """A single atomic transaction spanning the anchor row, the outbox row,
    and the idempotency_keys row.

    Implementations are async context managers that commit on clean exit
    and roll back on exception.
    """

    @abstractmethod
    async def __aenter__(self) -> "UnitOfWork":
        ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb) -> None:
        ...

    @abstractmethod
    async def commit(self) -> None:
        ...

    @abstractmethod
    async def rollback(self) -> None:
        ...

    # The three repositories scoped to this UoW.
    anchors: "AnchorRepository"
    outbox: "OutboxRepository"
    idempotency: "IdempotencyRepository"


class UnitOfWorkFactory(ABC):
    @abstractmethod
    def __call__(self) -> UnitOfWork:
        """Construct (don't enter) a new UoW."""


class AnchorRepository(ABC):
    @abstractmethod
    async def insert(self, anchor: IdentityAnchor) -> None:
        ...

    @abstractmethod
    async def get(self, internal_id: str) -> IdentityAnchor | None:
        """Load the aggregate from the write-side ``anchor`` table.

        Returns ``None`` when no row matches. Used by every lifecycle
        handler (UPDATE / ARCHIVE / RESTORE / PSEUDONYMISE) to rehydrate
        the aggregate before applying the command.
        """

    @abstractmethod
    async def update(self, anchor: IdentityAnchor) -> None:
        """Persist the post-transition state of an existing aggregate row.

        Implementations must write the full set of mutable columns of
        ``anchor`` (PII, anchor_status, revision, pseudonymized_at,
        last_processed_command_id, updated_at) WHERE internal_id matches.
        """


class OutboxRepository(ABC):
    @abstractmethod
    async def append(
        self,
        *,
        message_id: str,
        correlation_id: str,
        causation_id: str | None,
        schema_id: str,
        schema_version: str,
        routing_key: str,
        exchange: str,
        occurred_at: datetime,
        actor: dict[str, Any],
        payload: dict[str, Any],
    ) -> None:
        ...


class IdempotencyRepository(ABC):
    """Idempotency keys with a 30-day window."""

    WINDOW_DAYS = 30

    @abstractmethod
    async def get(self, scope: str, key: str) -> dict[str, Any] | None:
        """Return the stored idempotency record (incl. response_body + internal_id)
        if a prior call within the 30-day window registered it; ``None`` otherwise.
        """

    @abstractmethod
    async def remember(
        self,
        *,
        scope: str,
        key: str,
        internal_id: str,
        response_body: dict[str, Any],
        response_code: int,
    ) -> None:
        ...


class AnchorDirectoryReader(ABC):
    """Read-side port — backs QRY.GET_ANCHOR."""

    @abstractmethod
    async def get(self, internal_id: str) -> dict[str, Any] | None:
        """Return the projection row or ``None`` on miss."""


class AnchorDirectoryWriter(ABC):
    """Read-side port — backs the projection consumer."""

    @abstractmethod
    async def upsert(self, projection_row: dict[str, Any]) -> bool:
        """Apply last-write-wins upsert. Returns True if applied, False if
        the incoming revision was ≤ the stored revision (out-of-order drop).
        """


class SchemaValidator(ABC):
    @abstractmethod
    def validate_payload(self, payload: dict[str, Any]) -> None:
        """Raise ``jsonschema.ValidationError`` if invalid; return None otherwise."""


class EventPublisher(ABC):
    @abstractmethod
    async def publish(
        self,
        *,
        exchange: str,
        routing_key: str,
        body: bytes,
        headers: dict[str, str],
        message_id: str,
        correlation_id: str,
    ) -> None:
        ...
