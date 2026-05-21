"""Outbox relay — polls PENDING rows and publishes them.

ADR-TECH-STRAT-001 Rule 3 — at-least-once delivery. The relay marks rows
``PUBLISHED`` only after a successful broker ack. If publication fails, the
row stays ``PENDING`` and is retried on the next poll cycle.

Single-instance for TASK-002 (the ``outbox_relay_state`` table is a
placeholder for future leader-election). The relay processes rows in
ID order to preserve emission order per aggregate (the rows are inserted in
the same order as the underlying anchor transitions).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .publisher import AioPikaPublisher

log = structlog.get_logger()


class OutboxRelay:
    def __init__(
        self,
        *,
        pool: AsyncConnectionPool,
        publisher: AioPikaPublisher,
        poll_interval_seconds: float = 0.5,
        batch_size: int = 50,
    ) -> None:
        self._pool = pool
        self._publisher = publisher
        self._poll_interval = poll_interval_seconds
        self._batch_size = batch_size
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        await self._publisher.ensure_exchange()
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="outbox-relay")
        log.info("outbox_relay.started")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None
        log.info("outbox_relay.stopped")

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                processed = await self.drain_once()
                if processed == 0:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval)
            except asyncio.TimeoutError:
                continue
            except Exception:  # noqa: BLE001 — relay must never crash the worker
                log.exception("outbox_relay.poll_failed")
                await asyncio.sleep(self._poll_interval)

    async def drain_once(self) -> int:
        """Pop up to ``batch_size`` PENDING rows in a serialised transaction.

        Returns the number of rows successfully published.
        """
        async with self._pool.connection() as conn:
            await conn.set_autocommit(False)
            try:
                async with conn.cursor(row_factory=dict_row) as cur:
                    # SKIP LOCKED — defends a future multi-relay deployment.
                    await cur.execute(
                        """
                        SELECT id, message_id, correlation_id, routing_key, exchange, payload
                        FROM outbox
                        WHERE status = 'PENDING'
                        ORDER BY id
                        LIMIT %s
                        FOR UPDATE SKIP LOCKED
                        """,
                        (self._batch_size,),
                    )
                    rows = await cur.fetchall()

                if not rows:
                    await conn.rollback()
                    return 0

                published_ids: list[int] = []
                for row in rows:
                    payload: dict[str, Any] = row["payload"]
                    if isinstance(payload, str):
                        payload = json.loads(payload)
                    body = json.dumps(payload, separators=(",", ":")).encode()
                    try:
                        await self._publisher.publish(
                            exchange=row["exchange"],
                            routing_key=row["routing_key"],
                            body=body,
                            headers={
                                "schema_id": payload["envelope"].get("emitting_capability", ""),
                            },
                            message_id=str(row["message_id"]),
                            correlation_id=str(row["correlation_id"]),
                        )
                    except Exception:  # noqa: BLE001
                        log.exception(
                            "outbox_relay.publish_failed",
                            outbox_id=row["id"],
                            message_id=str(row["message_id"]),
                        )
                        # Bump the attempts counter; leave status PENDING.
                        async with conn.cursor() as cur:
                            await cur.execute(
                                """
                                UPDATE outbox
                                SET attempts = attempts + 1, last_error = %s
                                WHERE id = %s
                                """,
                                ("publish_failed", row["id"]),
                            )
                        continue
                    published_ids.append(row["id"])

                if published_ids:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            """
                            UPDATE outbox
                            SET status = 'PUBLISHED', published_at = NOW()
                            WHERE id = ANY(%s)
                            """,
                            (published_ids,),
                        )

                await conn.commit()
                log.info("outbox_relay.batch", published=len(published_ids))
                return len(published_ids)
            except Exception:
                await conn.rollback()
                raise
