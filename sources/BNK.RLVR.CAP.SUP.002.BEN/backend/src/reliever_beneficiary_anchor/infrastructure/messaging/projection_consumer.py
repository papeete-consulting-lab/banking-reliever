"""Projection consumer — listens on a dedicated queue bound to
``sup.002.ben-events`` with the canonical routing key and feeds
``PRJ.ANCHOR_DIRECTORY``.

Last-write-wins on (internal_id, revision) per read-models.yaml. Manual
ack only after the projection upsert succeeds (at-least-once on the read
side too).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, date as _date

import structlog
from aio_pika import ExchangeType
from aio_pika.abc import AbstractRobustConnection, AbstractIncomingMessage

from ...application.ports import AnchorDirectoryWriter, SchemaValidator

log = structlog.get_logger()


class ProjectionConsumer:
    def __init__(
        self,
        *,
        connection: AbstractRobustConnection,
        exchange_name: str,
        routing_key: str,
        queue_name: str,
        writer: AnchorDirectoryWriter,
        validator: SchemaValidator,
    ) -> None:
        self._connection = connection
        self._exchange_name = exchange_name
        self._routing_key = routing_key
        self._queue_name = queue_name
        self._writer = writer
        self._validator = validator
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        channel = await self._connection.channel()
        await channel.set_qos(prefetch_count=32)
        exchange = await channel.declare_exchange(
            self._exchange_name, ExchangeType.TOPIC, durable=True
        )
        queue = await channel.declare_queue(self._queue_name, durable=True)
        await queue.bind(exchange, routing_key=self._routing_key)
        log.info(
            "projection_consumer.bound",
            exchange=self._exchange_name,
            routing_key=self._routing_key,
            queue=self._queue_name,
        )
        await queue.consume(self._on_message, no_ack=False)

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process(requeue=True, ignore_processed=True):
            body = message.body
            try:
                payload = json.loads(body)
            except Exception:
                log.exception("projection_consumer.json_decode_failed")
                raise

            try:
                self._validator.validate_payload(payload)
            except Exception:
                # A schema-invalid message MUST not be silently dropped — log
                # loudly. The infra-layer dead-lettering policy lands later.
                log.exception(
                    "projection_consumer.schema_invalid",
                    message_id=str(message.message_id),
                )
                raise

            projection_row = {
                "internal_id":      payload["internal_id"],
                "last_name":        payload.get("last_name"),
                "first_name":       payload.get("first_name"),
                "date_of_birth":    _date.fromisoformat(payload["date_of_birth"])
                                    if payload.get("date_of_birth") else None,
                "contact_details":  payload.get("contact_details"),
                "anchor_status":    payload["anchor_status"],
                "creation_date":    _date.fromisoformat(payload["creation_date"]),
                "pseudonymized_at": datetime.fromisoformat(payload["pseudonymized_at"])
                                    if payload.get("pseudonymized_at") else None,
                "revision":         int(payload["revision"]),
            }
            applied = await self._writer.upsert(projection_row)
            log.info(
                "projection_consumer.processed",
                internal_id=projection_row["internal_id"],
                revision=projection_row["revision"],
                applied=applied,
            )
