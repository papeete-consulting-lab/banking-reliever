"""Publisher behaviour tests — broker-free.

We replace ``aio_pika.connect_robust`` with a stub so the publisher can be
driven end-to-end without RabbitMQ running. The tests assert:

- ``publish_one`` produces a schema-valid payload for every transition kind.
- The published RabbitMQ message carries the right routing key, message_id
  and headers.
- ``STUB_ACTIVE=false`` keeps the publisher from connecting at all.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from reliever_beneficiary_identity_anchor_stub.payload_factory import TRANSITION_KINDS
from reliever_beneficiary_identity_anchor_stub.publisher import StubPublisher
from reliever_beneficiary_identity_anchor_stub.schema_validator import validate
from reliever_beneficiary_identity_anchor_stub.settings import (
    StubSettings,
    get_settings,
    reset_settings_cache,
)


# ── in-memory aio-pika doubles ────────────────────────────────────────


@dataclass
class _CapturedPublish:
    routing_key: str
    body: bytes
    message_id: str
    headers: dict[str, Any]


class _FakeExchange:
    def __init__(self) -> None:
        self.publishes: list[_CapturedPublish] = []

    async def publish(self, message, routing_key: str) -> None:
        self.publishes.append(
            _CapturedPublish(
                routing_key=routing_key,
                body=message.body,
                message_id=str(message.message_id),
                headers=dict(message.headers or {}),
            )
        )


class _FakeChannel:
    def __init__(self, exchange: _FakeExchange) -> None:
        self._exchange = exchange

    async def declare_exchange(self, name: str, type_, *, durable: bool):  # noqa: ANN001
        return self._exchange


class _FakeConnection:
    def __init__(self, exchange: _FakeExchange) -> None:
        self._exchange = exchange
        self.closed = False

    async def channel(self) -> _FakeChannel:
        return _FakeChannel(self._exchange)

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def settings_active(monkeypatch: pytest.MonkeyPatch) -> StubSettings:
    monkeypatch.setenv("RELIEVER_STUB_ACTIVE", "true")
    reset_settings_cache()
    return get_settings()


@pytest.fixture
def settings_inactive(monkeypatch: pytest.MonkeyPatch) -> StubSettings:
    monkeypatch.setenv("RELIEVER_STUB_ACTIVE", "false")
    reset_settings_cache()
    return get_settings()


# ── test the inactive path ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publisher_inactive_does_not_connect(
    settings_inactive: StubSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """STUB_ACTIVE=false → connect_robust must NOT be called."""
    called: list[str] = []

    async def fake_connect_robust(_url: str):
        called.append("connect")
        raise AssertionError("must not connect when STUB_ACTIVE=false")

    monkeypatch.setattr(
        "reliever_beneficiary_identity_anchor_stub.publisher.aio_pika.connect_robust",
        fake_connect_robust,
    )

    pub = StubPublisher(settings_inactive)
    await pub.start()
    assert called == []
    await pub.stop()


# ── publish_one happy path ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_one_produces_valid_payload_per_kind(
    settings_active: StubSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    exchange = _FakeExchange()
    connection = _FakeConnection(exchange)

    async def fake_connect_robust(_url: str):
        return connection

    monkeypatch.setattr(
        "reliever_beneficiary_identity_anchor_stub.publisher.aio_pika.connect_robust",
        fake_connect_robust,
    )

    pub = StubPublisher(settings_active)
    await pub.start()
    # Defeat the background loop — we only want to test publish_one.
    if pub._task is not None:
        pub._task.cancel()

    for kind in TRANSITION_KINDS:
        payload = await pub.publish_one(kind)
        validate(payload, settings_active.rvt_schema_path)

    await pub.stop()

    assert len(exchange.publishes) == len(TRANSITION_KINDS)
    # Every captured publish has the right routing key.
    for cap in exchange.publishes:
        assert cap.routing_key == settings_active.bus_routing_key
        body = json.loads(cap.body)
        # Re-validate the wire-encoded payload as a safety belt.
        validate(body, settings_active.rvt_schema_path)
        assert body["envelope"]["message_id"] == cap.message_id
        assert cap.headers["emitting_capability"] == "BNK.RLVR.CAP.SUP.002.BEN"
        assert cap.headers["resource_event"] == "BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED"
        assert cap.headers["business_event"] == "BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED"


@pytest.mark.asyncio
async def test_publish_covers_all_5_kinds(
    settings_active: StubSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    exchange = _FakeExchange()
    connection = _FakeConnection(exchange)
    monkeypatch.setattr(
        "reliever_beneficiary_identity_anchor_stub.publisher.aio_pika.connect_robust",
        lambda _url: _async_return(connection),
    )

    pub = StubPublisher(settings_active)
    await pub.start()
    if pub._task is not None:
        pub._task.cancel()

    for kind in TRANSITION_KINDS:
        await pub.publish_one(kind)

    await pub.stop()

    kinds = {json.loads(p.body)["transition_kind"] for p in exchange.publishes}
    assert kinds == set(TRANSITION_KINDS)


def _async_return(value):
    async def _impl():
        return value

    return _impl()
