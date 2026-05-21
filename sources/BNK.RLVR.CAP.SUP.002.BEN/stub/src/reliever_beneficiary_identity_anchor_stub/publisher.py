"""aio-pika publisher — emits synthetic RVT events on the topic exchange.

Topology (from process/BNK.RLVR.CAP.SUP.002.BEN/bus.yaml + ADR-TECH-STRAT-001):
  exchange       : sup.002.ben-events (topic, durable, owned by BNK.RLVR.CAP.SUP.002.BEN)
  routing key    : BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED
  payload schema : process/BNK.RLVR.CAP.SUP.002.BEN/schemas/BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json

Cadence is configurable via env vars (``RELIEVER_CADENCE_MIN_PER_MINUTE`` /
``RELIEVER_CADENCE_MAX_PER_MINUTE``); default 1–10 events / minute.

Toggling ``RELIEVER_STUB_ACTIVE=false`` halts publication.
"""
from __future__ import annotations

import asyncio
import json
import random
from typing import Any

import aio_pika
import structlog

from .payload_factory import TransitionCycler, build_event
from .schema_validator import validate
from .settings import StubSettings

log = structlog.get_logger(__name__)


class StubPublisher:
    """Lifespan-managed RabbitMQ publisher.

    On :meth:`start`, connects to RabbitMQ, declares the topic exchange
    (durable, owned by this capability), and kicks off the background
    emission loop. On :meth:`stop`, cancels the loop and closes the
    connection.
    """

    def __init__(self, settings: StubSettings) -> None:
        self._settings = settings
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None
        self._task: asyncio.Task | None = None
        self._cycler = TransitionCycler()

    async def start(self) -> None:
        if not self._settings.stub_active:
            log.info(
                "publisher.disabled",
                reason="RELIEVER_STUB_ACTIVE=false",
                exchange=self._settings.bus_exchange,
            )
            return

        log.info("publisher.connecting", amqp_url=self._settings.amqp_url)
        self._connection = await aio_pika.connect_robust(self._settings.amqp_url)
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            self._settings.bus_exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        log.info(
            "publisher.exchange_declared",
            exchange=self._settings.bus_exchange,
            type="topic",
            durable=True,
            owned_by=self._settings.capability_id,
        )

        self._task = asyncio.create_task(self._loop(), name="stub-publisher-loop")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._connection is not None:
            await self._connection.close()
        log.info("publisher.stopped")

    async def _loop(self) -> None:
        """Background loop — picks a transition kind every tick, builds an
        event, validates it against the schema, and publishes it.
        """
        log.info(
            "publisher.loop.start",
            cadence=(
                self._settings.cadence_min_per_minute,
                self._settings.cadence_max_per_minute,
            ),
        )
        try:
            while True:
                if not self._settings.stub_active:
                    # Allow runtime toggle — re-read settings if needed.
                    await asyncio.sleep(1.0)
                    continue
                rate = random.uniform(
                    max(self._settings.cadence_min_per_minute, 1),
                    max(self._settings.cadence_max_per_minute, 1),
                )
                interval = 60.0 / rate
                kind = self._cycler.next_kind()
                try:
                    await self.publish_one(kind)
                except Exception:  # noqa: BLE001
                    log.exception("publisher.loop.publish_failed", kind=kind)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            log.info("publisher.loop.cancelled")
            raise

    async def publish_one(self, transition_kind: str) -> dict[str, Any]:
        """Build, validate, and publish a single event of the given kind.

        Returns the published payload (useful for tests).
        """
        if self._exchange is None:
            raise RuntimeError("publisher not started")

        payload = build_event(transition_kind=transition_kind)
        # Fail-fast on contract drift.
        validate(payload, self._settings.rvt_schema_path, schema_id=self._settings.bus_resource_event)

        body = json.dumps(payload).encode("utf-8")
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            message_id=payload["envelope"]["message_id"],
            correlation_id=payload["envelope"]["correlation_id"],
            headers={
                "schema_version": payload["envelope"]["schema_version"],
                "emitting_capability": payload["envelope"]["emitting_capability"],
                "causation_id": payload["envelope"]["causation_id"],
                "resource_event": self._settings.bus_resource_event,
                "business_event": self._settings.bus_business_event,
                "transition_kind": transition_kind,
            },
        )
        await self._exchange.publish(message, routing_key=self._settings.bus_routing_key)
        log.info(
            "publisher.published",
            transition_kind=transition_kind,
            internal_id=payload["internal_id"],
            revision=payload["revision"],
            routing_key=self._settings.bus_routing_key,
            message_id=payload["envelope"]["message_id"],
        )
        return payload
