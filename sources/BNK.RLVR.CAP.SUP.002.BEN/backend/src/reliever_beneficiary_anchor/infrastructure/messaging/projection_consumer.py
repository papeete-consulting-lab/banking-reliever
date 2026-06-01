"""Projection consumer — listens on a dedicated queue bound to
``sup.002.ben-events`` with the canonical routing key and feeds BOTH
``PRJ.ANCHOR_DIRECTORY`` (last-write-wins on ``revision``) AND
``PRJ.ANCHOR_HISTORY`` (append-only, idempotent on
``(internal_id, revision)``).

Manual ack only after BOTH projection writes succeed (at-least-once on
the read side — duplicate redelivery is absorbed by the directory's
revision-monotonic WHERE clause and the history's composite-PK conflict
clause).

read-models.yaml sources for ``PRJ.ANCHOR_HISTORY``:

  internal_id        ← payload.internal_id
  revision           ← payload.revision
  transition_kind    ← payload.transition_kind
  command_id         ← payload.command_id        (nullable)
  right_exercise_id  ← payload.right_exercise_id (PSEUDONYMISED only)
  actor              ← envelope.actor            (RVT envelope per
                                                  ADR-TECH-STRAT-003 —
                                                  NOT re-captured here)
  occurred_at        ← payload.occurred_at
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, date as _date

import structlog
from aio_pika import ExchangeType
from aio_pika.abc import AbstractRobustConnection, AbstractIncomingMessage

from ...application.ports import (
    AnchorDirectoryWriter,
    AnchorHistoryWriter,
    SchemaValidator,
)

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
        history_writer: AnchorHistoryWriter,
        validator: SchemaValidator,
    ) -> None:
        self._connection = connection
        self._exchange_name = exchange_name
        self._routing_key = routing_key
        self._queue_name = queue_name
        self._writer = writer
        self._history_writer = history_writer
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

            applied = await self._apply(payload)
            log.info(
                "projection_consumer.processed",
                internal_id=str(payload.get("internal_id")),
                revision=int(payload.get("revision", -1)),
                directory_applied=applied["directory"],
                history_applied=applied["history"],
            )

    async def _apply(self, payload: dict) -> dict[str, bool]:
        """Apply both projections for a single RVT.

        Public for the unit tests so the consumer's projection logic can
        be exercised without a live RabbitMQ connection.
        """
        directory_row = {
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

        # PII-free history row — only the seven fields declared in
        # read-models.yaml.PRJ.ANCHOR_HISTORY.fed_by. PII fields from the
        # payload are NEVER copied here, even if a hand-crafted RVT carries
        # them.
        envelope = payload.get("envelope") or {}
        actor = envelope.get("actor")
        if actor is None:
            # Defensive — the RVT JSON Schema mandates envelope.actor, so a
            # missing actor here is a contract violation upstream.
            raise ValueError(
                "RVT envelope.actor is required (per bus.yaml + ADR-TECH-STRAT-003)"
            )
        history_row = {
            "internal_id":       payload["internal_id"],
            "revision":          int(payload["revision"]),
            "transition_kind":   payload["transition_kind"],
            "command_id":        payload.get("command_id"),
            "right_exercise_id": payload.get("right_exercise_id"),
            "actor":             actor,
            "occurred_at":       datetime.fromisoformat(payload["occurred_at"]),
        }

        directory_applied = await self._writer.upsert(directory_row)
        history_applied = await self._history_writer.append(history_row)
        return {"directory": directory_applied, "history": history_applied}
