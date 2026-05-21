"""Application-layer tests for MintAnchorHandler — uses in-memory ports
so the test runs without Postgres or Rabbit.
"""

from __future__ import annotations

import copy
from datetime import date, datetime
from typing import Any

import pytest

from reliever_beneficiary_anchor.application.dto import MintAnchorCommandDto
from reliever_beneficiary_anchor.application.handlers import MintAnchorHandler
from reliever_beneficiary_anchor.application.ports import (
    AnchorRepository,
    IdempotencyRepository,
    OutboxRepository,
    UnitOfWork,
    UnitOfWorkFactory,
)
from reliever_beneficiary_anchor.domain.aggregate import IdentityAnchor
from reliever_beneficiary_anchor.domain.value_objects import Actor, ContactDetails
from reliever_beneficiary_anchor.infrastructure.schema_validation.loader import build_validators


# ─── In-memory ports ───────────────────────────────────────────────────


class _InMemoryAnchorRepo(AnchorRepository):
    def __init__(self) -> None:
        self.rows: list[IdentityAnchor] = []

    async def insert(self, anchor: IdentityAnchor) -> None:
        self.rows.append(anchor)

    async def get(self, internal_id: str) -> IdentityAnchor | None:
        for a in self.rows:
            if str(a.internal_id) == internal_id:
                return a
        return None

    async def update(self, anchor: IdentityAnchor) -> None:
        for i, existing in enumerate(self.rows):
            if existing.internal_id == anchor.internal_id:
                self.rows[i] = anchor
                return
        raise AssertionError(f"update() called on missing anchor {anchor.internal_id}")


class _InMemoryOutboxRepo(OutboxRepository):
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

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
        self.rows.append(
            {
                "message_id": message_id,
                "correlation_id": correlation_id,
                "causation_id": causation_id,
                "schema_id": schema_id,
                "schema_version": schema_version,
                "routing_key": routing_key,
                "exchange": exchange,
                "occurred_at": occurred_at,
                "actor": actor,
                "payload": payload,
            }
        )


class _InMemoryIdempotencyRepo(IdempotencyRepository):
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict[str, Any]] = {}

    async def get(self, scope: str, key: str) -> dict[str, Any] | None:
        return self.rows.get((scope, key))

    async def remember(
        self,
        *,
        scope: str,
        key: str,
        internal_id: str,
        response_body: dict[str, Any],
        response_code: int,
    ) -> None:
        self.rows.setdefault(
            (scope, key),
            {
                "scope": scope,
                "key": key,
                "internal_id": internal_id,
                "response_body": copy.deepcopy(response_body),
                "response_code": response_code,
            },
        )


class _InMemoryUoW(UnitOfWork):
    def __init__(self, anchors, outbox, idem):
        self.anchors = anchors
        self.outbox = outbox
        self.idempotency = idem
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class _InMemoryUoWFactory(UnitOfWorkFactory):
    def __init__(self):
        self.anchors = _InMemoryAnchorRepo()
        self.outbox = _InMemoryOutboxRepo()
        self.idem = _InMemoryIdempotencyRepo()
        self.uows: list[_InMemoryUoW] = []

    def __call__(self) -> _InMemoryUoW:
        u = _InMemoryUoW(self.anchors, self.outbox, self.idem)
        self.uows.append(u)
        return u


# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def validators(schemas_dir):
    return build_validators(schemas_dir)


@pytest.fixture
def factory():
    return _InMemoryUoWFactory()


@pytest.fixture
def handler(factory, validators):
    _, rvt_v = validators
    return MintAnchorHandler(uow_factory=factory, rvt_validator=rvt_v)


def _cmd(crid: str = "018f8e10-aaaa-7000-8000-000000000001") -> MintAnchorCommandDto:
    return MintAnchorCommandDto(
        client_request_id=crid,
        last_name="Dupont",
        first_name="Marie",
        date_of_birth=date(1985, 6, 21),
        contact_details=ContactDetails(email="marie.dupont@example.org"),
        actor=Actor(kind="human", subject="018f8e10-2222-7000-8000-000000000001"),
    )


# ─── Tests ─────────────────────────────────────────────────────────────


class TestMintHandler:
    async def test_first_call_returns_201(self, handler, factory):
        result = await handler.handle(_cmd())
        assert result.http_status == 201
        assert result.idempotent_replay is False
        assert result.anchor.revision == 1
        assert result.anchor.anchor_status == "ACTIVE"
        assert len(factory.anchors.rows) == 1
        assert len(factory.outbox.rows) == 1
        assert len(factory.idem.rows) == 1

    async def test_outbox_row_carries_canonical_routing_key(self, handler, factory):
        await handler.handle(_cmd())
        row = factory.outbox.rows[0]
        assert row["exchange"] == "sup.002.ben-events"
        assert row["routing_key"] == (
            "BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED."
            "BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED"
        )

    async def test_outbox_payload_validates_against_rvt_schema(self, handler, factory, validators):
        await handler.handle(_cmd())
        _, rvt_validator = validators
        rvt_validator.validate_payload(factory.outbox.rows[0]["payload"])
        # No raise → contract-compatible.

    async def test_envelope_carries_uuidv7_trio_and_actor(self, handler, factory):
        await handler.handle(_cmd())
        envelope = factory.outbox.rows[0]["payload"]["envelope"]
        for f in ("message_id", "correlation_id", "causation_id"):
            assert envelope[f]  # set, non-empty
        actor = envelope["actor"]
        assert actor["kind"] == "human"
        assert actor["subject"] == "018f8e10-2222-7000-8000-000000000001"

    async def test_transition_kind_minted_and_revision_1(self, handler, factory):
        await handler.handle(_cmd())
        payload = factory.outbox.rows[0]["payload"]
        assert payload["transition_kind"] == "MINTED"
        assert payload["revision"] == 1

    async def test_idempotent_replay_returns_200_and_no_new_row(self, handler, factory):
        crid = "018f8e10-aaaa-7000-8000-000000000002"
        first = await handler.handle(_cmd(crid=crid))
        assert first.http_status == 201

        second = await handler.handle(_cmd(crid=crid))
        assert second.http_status == 200
        assert second.idempotent_replay is True
        assert second.error_code == "REQUEST_ALREADY_PROCESSED"
        # Identical anchor returned.
        assert second.anchor.internal_id == first.anchor.internal_id
        # No extra anchor row, no extra outbox row, no extra idempotency row.
        assert len(factory.anchors.rows) == 1
        assert len(factory.outbox.rows) == 1
        assert len(factory.idem.rows) == 1

    async def test_correlation_id_equals_internal_id(self, handler, factory):
        await handler.handle(_cmd())
        envelope = factory.outbox.rows[0]["payload"]["envelope"]
        payload = factory.outbox.rows[0]["payload"]
        assert envelope["correlation_id"] == payload["internal_id"]

    async def test_causation_id_equals_command_id(self, handler, factory):
        await handler.handle(_cmd())
        envelope = factory.outbox.rows[0]["payload"]["envelope"]
        payload = factory.outbox.rows[0]["payload"]
        assert envelope["causation_id"] == payload["command_id"]
