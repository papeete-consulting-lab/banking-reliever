"""Async aio-pika publisher.

Declares the owned topic exchange (idempotent, durable=true) and
publishes each Emission with the corresponding routing key. Schema
validation runs BEFORE publish — an invalid payload is never put on the
wire (the publish call raises and the worker logs + skips).

The publisher exposes a `publish_emissions(emissions)` coroutine; the
worker (in __main__) drives the cadence and feeds it batches.
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncIterator, Iterable

from .config import StubConfig
from .fixtures import Emission
from .schema_validator import SchemaValidator


if TYPE_CHECKING:  # pragma: no cover — type-only import
    import aio_pika  # noqa: F401


logger = logging.getLogger(__name__)


def _require_aio_pika():
    """Import aio-pika lazily so that tests can import this module
    without the runtime dependency installed.

    Returns the module object on success; raises ImportError with a
    helpful message otherwise.
    """
    try:
        import aio_pika  # noqa: PLC0415

        return aio_pika
    except ImportError as exc:  # pragma: no cover — environment-dependent
        raise ImportError(
            "aio-pika is required to run the stub worker. "
            "Install with: pip install -r requirements.txt"
        ) from exc


@dataclass
class PublishStats:
    published: int = 0
    rejected_by_schema: int = 0


class Publisher:
    """Encapsulates the AMQP connection + channel + exchange handle.

    The constructor takes opaque `Any` because the tests inject mocks
    and a recording stand-in exchange. The production wiring (in
    `open_publisher`) supplies real aio-pika objects.
    """

    def __init__(
        self,
        *,
        connection: Any,
        channel: Any,
        exchange: Any,
        validator: SchemaValidator,
    ) -> None:
        self._conn = connection
        self._channel = channel
        self._exchange = exchange
        self._validator = validator
        self.stats = PublishStats()

    async def publish_emissions(self, emissions: Iterable[Emission]) -> None:
        """Validate then publish every emission in `emissions`.

        Atomicity: callers pass the CURRENT + THRESHOLD pair as ONE
        iterable, so they ship in the same loop iteration. We do not
        rely on RabbitMQ transactions — the contract is "the publisher
        does not emit one without the other", which we honour by
        construction (fixtures.build_recomputation_emissions returns
        them paired).
        """
        for em in emissions:
            try:
                self._validator.validate(em.rvt_id, em.payload)
            except Exception as exc:  # noqa: BLE001
                self.stats.rejected_by_schema += 1
                logger.error(
                    "Schema validation FAILED for %s — payload NOT published. err=%s",
                    em.rvt_id,
                    exc,
                )
                # Fail fast: re-raise to make the worker loop notice. The
                # contract is "no invalid payload on the wire" — silent
                # skipping would mask bugs.
                raise

            body = json.dumps(em.payload, separators=(",", ":")).encode("utf-8")
            message = self._build_message(em, body)
            await self._exchange.publish(message, routing_key=em.routing_key)
            self.stats.published += 1
            logger.info(
                "PUB %s key=%s msg_id=%s case_id=%s",
                em.rvt_id,
                em.routing_key,
                em.payload["envelope"]["message_id"],
                em.payload["case_id"],
            )

    def _build_message(self, em: Emission, body: bytes):
        """Build an aio-pika Message. Falls back to a lightweight
        stand-in object when aio-pika is not installed (test-only)."""
        headers = {
            "rvt_id": em.rvt_id,
            "schema_version": em.payload["envelope"]["schema_version"],
            "emitting_capability": em.payload["envelope"]["emitting_capability"],
            "causation_id": em.payload["envelope"]["causation_id"],
        }
        try:
            aio_pika = _require_aio_pika()
        except ImportError:
            # Test fallback — a minimal duck-typed object exposing the
            # attributes the test suite inspects.
            class _StubMessage:
                pass

            m = _StubMessage()
            m.body = body
            m.headers = headers
            m.message_id = em.payload["envelope"]["message_id"]
            m.correlation_id = em.payload["envelope"]["correlation_id"]
            m.content_type = "application/json"
            return m

        return aio_pika.Message(
            body=body,
            content_type="application/json",
            content_encoding="utf-8",
            message_id=em.payload["envelope"]["message_id"],
            correlation_id=em.payload["envelope"]["correlation_id"],
            headers=headers,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )


@asynccontextmanager
async def open_publisher(
    *, cfg: StubConfig, validator: SchemaValidator
) -> AsyncIterator[Publisher]:
    """Open an AMQP connection and declare the owned exchange idempotently."""
    aio_pika = _require_aio_pika()
    logger.info("Connecting to RabbitMQ at %s", cfg.rabbitmq_url)
    connection = await aio_pika.connect_robust(cfg.rabbitmq_url)
    try:
        channel = await connection.channel()
        # Publisher confirms for durability — recommended on persistent exchanges.
        await channel.set_qos(prefetch_count=1)

        exchange = await channel.declare_exchange(
            name=cfg.exchange_name,
            type=aio_pika.ExchangeType.TOPIC,
            durable=True,
            auto_delete=False,
        )
        logger.info(
            "Declared topic exchange '%s' (durable=true, owner=BNK.RLVR.CAP.BSP.001.SCO)",
            cfg.exchange_name,
        )

        yield Publisher(
            connection=connection,
            channel=channel,
            exchange=exchange,
            validator=validator,
        )
    finally:
        await connection.close()
        logger.info("RabbitMQ connection closed.")
