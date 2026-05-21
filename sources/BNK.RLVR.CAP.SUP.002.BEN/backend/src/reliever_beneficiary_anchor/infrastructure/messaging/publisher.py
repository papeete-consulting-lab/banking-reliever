"""aio-pika publisher — declares the topic exchange owned by this capability
and publishes pre-validated payloads.
"""

from __future__ import annotations

import structlog
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractRobustConnection, AbstractRobustExchange

from ...application.ports import EventPublisher

log = structlog.get_logger()


class AioPikaPublisher(EventPublisher):
    def __init__(self, connection: AbstractRobustConnection, exchange_name: str) -> None:
        self._connection = connection
        self._exchange_name = exchange_name
        self._exchange: AbstractRobustExchange | None = None

    async def ensure_exchange(self) -> AbstractRobustExchange:
        if self._exchange is not None:
            return self._exchange
        channel = await self._connection.channel()
        self._exchange = await channel.declare_exchange(
            self._exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )
        log.info("exchange.declared", exchange=self._exchange_name)
        return self._exchange

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
        if exchange != self._exchange_name:
            raise ValueError(
                f"Publisher is bound to {self._exchange_name!r}, refusing to publish to {exchange!r}"
            )
        ex = await self.ensure_exchange()
        msg = Message(
            body=body,
            headers=headers,
            message_id=message_id,
            correlation_id=correlation_id,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
        )
        await ex.publish(msg, routing_key=routing_key)
