"""PRJ.SUP.002.BEN.ANCHOR_HISTORY — read-side adapters (TASK-006).

The reader serves ``QRY.GET_ANCHOR_HISTORY``; the writer is invoked by
the projection consumer when an RVT lands.

Schema (see migrations/003_anchor_history.sql):

    anchor_history (
        internal_id        UUID         NOT NULL,
        revision           INTEGER      NOT NULL,
        transition_kind    TEXT         NOT NULL,
        command_id         UUID,
        right_exercise_id  UUID,
        actor              JSONB        NOT NULL,
        occurred_at        TIMESTAMPTZ  NOT NULL,
        recorded_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        PRIMARY KEY (internal_id, revision)
    )

The PII-free invariant is structural — the projection has NO PII
columns. Even if a hand-crafted RVT carries PII in its payload, the
writer extracts ONLY the seven fields enumerated in
``read-models.yaml.PRJ.ANCHOR_HISTORY.fed_by`` (sourced from envelope.actor
+ six payload fields) and discards the rest.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ...application.ports import (
    AnchorHistoryReader,
    AnchorHistoryWriter,
    RetentionPurger,
)


def compute_history_etag(rows: list[dict[str, Any]]) -> str:
    """ETag for a history response = sha256 over the (internal_id, revision)
    sequence + the last occurred_at. Bumps on every new row, which is
    what audit consumers want (read-after-write semantics per api.yaml).

    Empty list returns a deterministic empty marker — the presentation
    layer should NOT call this for 404 cases (no rows → 404, not 200).
    """
    if not rows:
        # Defensive — caller should map to 404 before reaching here.
        return 'W/"empty"'
    last = rows[-1]
    raw = (
        f"{last['internal_id']}|"
        f"{len(rows)}|"
        f"{int(last['revision'])}|"
        f"{last['occurred_at'].isoformat() if isinstance(last['occurred_at'], datetime) else last['occurred_at']}"
    ).encode()
    return f'W/"{hashlib.sha256(raw).hexdigest()[:24]}"'


class PostgresAnchorHistoryWriter(AnchorHistoryWriter):
    """Append-only writer. Idempotent on ``(internal_id, revision)`` —
    the composite primary key absorbs a duplicate delivery without
    raising; the ON CONFLICT DO NOTHING clause makes that explicit and
    cheap.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def append(self, row: dict[str, Any]) -> bool:
        internal_id = str(row["internal_id"])
        revision = int(row["revision"])
        transition_kind = str(row["transition_kind"])
        command_id = row.get("command_id")
        right_exercise_id = row.get("right_exercise_id")
        actor = row["actor"]
        if isinstance(actor, str):
            actor = json.loads(actor)
        occurred_at = row["occurred_at"]

        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO anchor_history (
                    internal_id, revision, transition_kind, command_id,
                    right_exercise_id, actor, occurred_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (internal_id, revision) DO NOTHING
                RETURNING internal_id
                """,
                (
                    internal_id,
                    revision,
                    transition_kind,
                    command_id,
                    right_exercise_id,
                    Jsonb(actor),
                    occurred_at,
                ),
            )
            applied = await cur.fetchone()
            await conn.commit()
            return applied is not None


class PostgresAnchorHistoryReader(AnchorHistoryReader):
    """List reader. Strict ascending ``revision`` order — the contract
    declared in ``api.yaml.getAnchorHistory``.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def list(
        self,
        *,
        internal_id: str,
        since_revision: int | None = None,
    ) -> list[dict[str, Any]]:
        async with (
            self._pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            if since_revision is None:
                await cur.execute(
                    """
                    SELECT internal_id, revision, transition_kind, command_id,
                           right_exercise_id, actor, occurred_at
                    FROM anchor_history
                    WHERE internal_id = %s
                    ORDER BY revision ASC
                    """,
                    (internal_id,),
                )
            else:
                await cur.execute(
                    """
                    SELECT internal_id, revision, transition_kind, command_id,
                           right_exercise_id, actor, occurred_at
                    FROM anchor_history
                    WHERE internal_id = %s
                      AND revision > %s
                    ORDER BY revision ASC
                    """,
                    (internal_id, since_revision),
                )
            return list(await cur.fetchall())


class PostgresRetentionPurger(RetentionPurger):
    """Range delete on ``occurred_at``. Single statement, returns the row
    count from ``DELETE ... RETURNING`` — psycopg's ``rowcount`` is the
    same value but more portable.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def purge_older_than(self, cutoff: datetime) -> int:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM anchor_history WHERE occurred_at < %s",
                (cutoff,),
            )
            await conn.commit()
            return cur.rowcount or 0
