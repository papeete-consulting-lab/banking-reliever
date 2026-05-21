"""PostgreSQL UoW + repositories — all three repositories share one connection
and one transaction. ADR-TECH-STRAT-001 Rule 3 (atomic outbox).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ...application.ports import (
    AnchorRepository,
    IdempotencyRepository,
    OutboxRepository,
    UnitOfWork,
    UnitOfWorkFactory,
)
from ...domain.aggregate import IdentityAnchor
from ...domain.value_objects import ContactDetails, PostalAddress


# ─── Repositories scoped to a single transaction ───────────────────────


class PostgresAnchorRepository(AnchorRepository):
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def insert(self, anchor: IdentityAnchor) -> None:
        contact = (
            anchor.pii.contact_details.to_dict() if anchor.pii.contact_details else None
        )
        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO anchor (
                    internal_id, last_name, first_name, date_of_birth, contact_details,
                    anchor_status, creation_date, pseudonymized_at, revision,
                    last_processed_command_id, last_processed_client_request_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(anchor.internal_id),
                    anchor.pii.last_name,
                    anchor.pii.first_name,
                    anchor.pii.date_of_birth,
                    Jsonb(contact) if contact is not None else None,
                    anchor.anchor_status,
                    anchor.creation_date,
                    anchor.pseudonymized_at,
                    anchor.revision,
                    anchor.last_processed_command_id,
                    anchor.last_processed_client_request_id,
                ),
            )

    async def get(self, internal_id: str) -> IdentityAnchor | None:
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT internal_id, last_name, first_name, date_of_birth, contact_details,
                       anchor_status, creation_date, pseudonymized_at, revision,
                       last_processed_command_id, last_processed_client_request_id
                FROM anchor
                WHERE internal_id = %s
                FOR UPDATE
                """,
                (internal_id,),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            contact_raw = row.get("contact_details")
            if isinstance(contact_raw, str):
                contact_raw = json.loads(contact_raw)
            contact = _contact_from_db(contact_raw)
            return IdentityAnchor.hydrate(
                internal_id=str(row["internal_id"]),
                last_name=row.get("last_name"),
                first_name=row.get("first_name"),
                date_of_birth=row.get("date_of_birth"),
                contact_details=contact,
                anchor_status=row["anchor_status"],
                creation_date=row["creation_date"],
                revision=row["revision"],
                pseudonymized_at=row.get("pseudonymized_at"),
                last_processed_command_id=(
                    str(row["last_processed_command_id"])
                    if row.get("last_processed_command_id") else None
                ),
                last_processed_client_request_id=(
                    str(row["last_processed_client_request_id"])
                    if row.get("last_processed_client_request_id") else None
                ),
            )

    async def update(self, anchor: IdentityAnchor) -> None:
        contact = (
            anchor.pii.contact_details.to_dict() if anchor.pii.contact_details else None
        )
        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE anchor
                SET last_name                 = %s,
                    first_name                = %s,
                    date_of_birth             = %s,
                    contact_details           = %s,
                    anchor_status             = %s,
                    pseudonymized_at          = %s,
                    revision                  = %s,
                    last_processed_command_id = %s,
                    updated_at                = NOW()
                WHERE internal_id = %s
                """,
                (
                    anchor.pii.last_name,
                    anchor.pii.first_name,
                    anchor.pii.date_of_birth,
                    Jsonb(contact) if contact is not None else None,
                    anchor.anchor_status,
                    anchor.pseudonymized_at,
                    anchor.revision,
                    anchor.last_processed_command_id,
                    str(anchor.internal_id),
                ),
            )


def _contact_from_db(raw: Any) -> ContactDetails | None:
    """Reconstruct a ``ContactDetails`` value object from a JSONB row payload."""
    if raw is None:
        return None
    postal_raw = raw.get("postal_address")
    postal = PostalAddress(**postal_raw) if isinstance(postal_raw, dict) else None
    return ContactDetails(
        email=raw.get("email"),
        phone=raw.get("phone"),
        postal_address=postal,
    )


class PostgresOutboxRepository(OutboxRepository):
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

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
        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO outbox (
                    message_id, correlation_id, causation_id, routing_key, exchange,
                    payload, schema_id, schema_version, occurred_at, actor, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING')
                """,
                (
                    message_id,
                    correlation_id,
                    causation_id,
                    routing_key,
                    exchange,
                    Jsonb(payload),
                    schema_id,
                    schema_version,
                    occurred_at,
                    Jsonb(actor),
                ),
            )


class PostgresIdempotencyRepository(IdempotencyRepository):
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def get(self, scope: str, key: str) -> dict[str, Any] | None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.WINDOW_DAYS)
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT scope, key, internal_id, response_body, response_code, created_at
                FROM idempotency_keys
                WHERE scope = %s AND key = %s AND created_at > %s
                """,
                (scope, key, cutoff),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            # response_body is stored as JSONB — psycopg gives us a dict already.
            body = row["response_body"]
            if isinstance(body, str):
                body = json.loads(body)
            row["response_body"] = body
            row["internal_id"] = str(row["internal_id"])
            return row

    async def remember(
        self,
        *,
        scope: str,
        key: str,
        internal_id: str,
        response_body: dict[str, Any],
        response_code: int,
    ) -> None:
        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO idempotency_keys (scope, key, internal_id, response_body, response_code)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (scope, key) DO NOTHING
                """,
                (scope, key, internal_id, Jsonb(response_body), response_code),
            )


# ─── Unit of Work ──────────────────────────────────────────────────────


class PostgresUnitOfWork(UnitOfWork):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool
        self._conn: AsyncConnection | None = None
        self._tx = None
        self.anchors: AnchorRepository  # type: ignore[assignment]
        self.outbox: OutboxRepository  # type: ignore[assignment]
        self.idempotency: IdempotencyRepository  # type: ignore[assignment]

    async def __aenter__(self) -> "PostgresUnitOfWork":
        self._conn = await self._pool.getconn()
        # psycopg autocommit defaults to False — explicit transaction starts on first command.
        await self._conn.set_autocommit(False)
        self.anchors = PostgresAnchorRepository(self._conn)
        self.outbox = PostgresOutboxRepository(self._conn)
        self.idempotency = PostgresIdempotencyRepository(self._conn)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._conn is None:
            return
        try:
            if exc_type is not None:
                await self._conn.rollback()
            # If neither commit() nor rollback() was called explicitly, roll
            # back to be safe (a UoW without commit is a no-op).
            else:
                # psycopg.AsyncConnection has no introspection for "in tx" —
                # call rollback() unconditionally on the connection's idle
                # branch is safe: rollback on idle is a no-op.
                try:
                    await self._conn.rollback()
                except psycopg.errors.NoActiveSqlTransaction:
                    pass
        finally:
            await self._pool.putconn(self._conn)
            self._conn = None

    async def commit(self) -> None:
        assert self._conn is not None
        await self._conn.commit()

    async def rollback(self) -> None:
        assert self._conn is not None
        await self._conn.rollback()


class PostgresUnitOfWorkFactory(UnitOfWorkFactory):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    def __call__(self) -> PostgresUnitOfWork:
        return PostgresUnitOfWork(self._pool)
