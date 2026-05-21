"""PRJ.SUP.002.BEN.ANCHOR_DIRECTORY — read-side adapters.

The reader serves QRY.GET_ANCHOR; the writer is invoked by the projection
consumer when an RVT lands.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ...application.ports import AnchorDirectoryReader, AnchorDirectoryWriter


def compute_etag(internal_id: str, revision: int) -> str:
    """ETag = sha256(internal_id|revision) truncated. Bumps on every revision
    update — the cache contract is "60s freshness window OR revision bump".
    """
    raw = f"{internal_id}|{revision}".encode()
    return f'W/"{hashlib.sha256(raw).hexdigest()[:24]}"'


class PostgresAnchorDirectoryReader(AnchorDirectoryReader):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def get(self, internal_id: str) -> dict[str, Any] | None:
        async with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT internal_id, last_name, first_name, date_of_birth, contact_details,
                       anchor_status, creation_date, pseudonymized_at, revision, updated_at, etag
                FROM anchor_directory
                WHERE internal_id = %s
                """,
                (internal_id,),
            )
            return await cur.fetchone()


class PostgresAnchorDirectoryWriter(AnchorDirectoryWriter):
    """Last-write-wins on revision. Drops events whose revision is ≤ the
    locally observed revision (out-of-order delivery protection per
    read-models.yaml.update_strategy).
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def upsert(self, projection_row: dict[str, Any]) -> bool:
        internal_id = str(projection_row["internal_id"])
        revision = int(projection_row["revision"])
        contact = projection_row.get("contact_details")
        if isinstance(contact, str):
            contact = json.loads(contact)
        etag = compute_etag(internal_id, revision)
        now = datetime.now(timezone.utc)

        async with self._pool.connection() as conn, conn.cursor() as cur:
            # INSERT ... ON CONFLICT with a WHERE clause that enforces the
            # revision-monotonic invariant. ``xmax = 0`` is true for inserts;
            # we detect "row applied" by checking RETURNING.
            await cur.execute(
                """
                INSERT INTO anchor_directory (
                    internal_id, last_name, first_name, date_of_birth, contact_details,
                    anchor_status, creation_date, pseudonymized_at, revision, updated_at, etag
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (internal_id) DO UPDATE SET
                    last_name        = EXCLUDED.last_name,
                    first_name       = EXCLUDED.first_name,
                    date_of_birth    = EXCLUDED.date_of_birth,
                    contact_details  = EXCLUDED.contact_details,
                    anchor_status    = EXCLUDED.anchor_status,
                    creation_date    = EXCLUDED.creation_date,
                    pseudonymized_at = EXCLUDED.pseudonymized_at,
                    revision         = EXCLUDED.revision,
                    updated_at       = EXCLUDED.updated_at,
                    etag             = EXCLUDED.etag
                WHERE anchor_directory.revision < EXCLUDED.revision
                RETURNING internal_id
                """,
                (
                    internal_id,
                    projection_row.get("last_name"),
                    projection_row.get("first_name"),
                    projection_row.get("date_of_birth"),
                    Jsonb(contact) if contact is not None else None,
                    projection_row["anchor_status"],
                    projection_row["creation_date"],
                    projection_row.get("pseudonymized_at"),
                    revision,
                    now,
                    etag,
                ),
            )
            row = await cur.fetchone()
            await conn.commit()
            return row is not None
