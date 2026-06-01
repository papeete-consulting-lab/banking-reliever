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
    the idempotency_keys row, and (for crypto-shredding) the
    anchor_crypto_keys row.

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

    # Repositories scoped to this UoW.
    anchors: "AnchorRepository"
    outbox: "OutboxRepository"
    idempotency: "IdempotencyRepository"
    crypto_keys: "CryptoKeyRepository"


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


class CryptoKeyRepository(ABC):
    """Per-anchor Data-Encryption-Key (DEK) lifecycle. Backs the chosen
    crypto-shredding strategy (per ADR-TECH-TACT-002) — each anchor row
    references one DEK; deleting the DEK row makes any at-rest ciphertext
    encoded under it mathematically unrecoverable.

    The implementation is in-postgres (single table) for the dev
    environment. A production deployment swaps this adapter for a Vault-
    transit-backed one — the port contract is unchanged.
    """

    @abstractmethod
    async def provision(self, *, crypto_key_id: str) -> None:
        """Insert a freshly-minted DEK row. Called at MINT time.

        Implementations source the key material from ``pgcrypto.gen_random_bytes(32)``
        (in-postgres) or from ``hvac.Client.secrets.transit.create_key`` /
        ``encrypt_data`` envelope encryption (Vault). The contract on the
        rest of the system is unchanged: the row exists after MINT, the
        anchor's ``crypto_key_id`` points at it.
        """

    @abstractmethod
    async def shred(self, *, crypto_key_id: str) -> None:
        """Crypto-shred — irreversibly delete the DEK row. Called at
        PSEUDONYMISE time. The anchor's ``crypto_key_id`` is severed by
        the ON DELETE SET NULL FK clause (and re-asserted to NULL by the
        anchor UPDATE in the same transaction).
        """

    @abstractmethod
    async def exists(self, *, crypto_key_id: str) -> bool:
        """Audit primitive — returns True iff the DEK row is still present.
        Used by integration tests to verify the observable post-condition
        of crypto-shredding (DEK destroyed).
        """


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
