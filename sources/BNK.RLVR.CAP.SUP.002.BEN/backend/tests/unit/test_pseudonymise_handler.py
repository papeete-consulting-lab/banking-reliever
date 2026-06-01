"""Application-layer tests for PseudonymiseAnchorHandler — TASK-005.

Uses in-memory ports so the test runs without Postgres or RabbitMQ.

Covers:
  * Happy path ACTIVE → PSEUDONYMISED:
      - 200, idempotent_replay=False
      - exactly one outbox row with transition_kind=PSEUDONYMISED
      - exactly one idempotency row
      - DEK row deleted (crypto-shredding observable post-condition)
      - anchor row has PII fields nulled, crypto_key_id severed
  * Happy path ARCHIVED → PSEUDONYMISED (INV.BEN.006).
  * Idempotent replay: duplicate command_id → 200,
      COMMAND_ALREADY_PROCESSED, NO second outbox row, NO second DEK shred.
  * RVT payload validates against the canonical schema's PSEUDONYMISED
    branch (PII null + right_exercise_id set + pseudonymized_at set).
  * Terminal-state guard: PSEUDONYMISED → 409 (AnchorAlreadyPseudonymised).
  * Missing anchor → AnchorNotFound.
"""

from __future__ import annotations

import copy
from datetime import date, datetime
from typing import Any

import pytest
from uuid_extensions import uuid7

from reliever_beneficiary_anchor.application.dto import (
    PseudonymiseAnchorCommandDto,
)
from reliever_beneficiary_anchor.application.handlers import (
    IDEMPOTENCY_SCOPE_PSEUDONYMISE,
    PseudonymiseAnchorHandler,
)
from reliever_beneficiary_anchor.application.ports import (
    AnchorRepository,
    IdempotencyRepository,
    OutboxRepository,
    UnitOfWork,
    UnitOfWorkFactory,
)
from reliever_beneficiary_anchor.domain.aggregate import IdentityAnchor
from reliever_beneficiary_anchor.domain.errors import (
    AnchorAlreadyPseudonymised,
    AnchorNotFound,
)
from reliever_beneficiary_anchor.domain.value_objects import (
    Actor,
    ContactDetails,
)
from reliever_beneficiary_anchor.infrastructure.schema_validation.loader import (
    build_validators_bundle,
)


_INTERNAL_ID = "018f8e10-9999-7000-8000-00000000aaaa"


def _uuidv7() -> str:
    return str(uuid7())


# ─── In-memory ports ───────────────────────────────────────────────────


class _InMemoryAnchorRepo(AnchorRepository):
    def __init__(self) -> None:
        self.rows: dict[str, IdentityAnchor] = {}

    async def insert(self, anchor: IdentityAnchor) -> None:
        self.rows[str(anchor.internal_id)] = anchor

    async def get(self, internal_id: str) -> IdentityAnchor | None:
        existing = self.rows.get(internal_id)
        if existing is None:
            return None
        return IdentityAnchor.hydrate(
            internal_id=str(existing.internal_id),
            last_name=existing.pii.last_name,
            first_name=existing.pii.first_name,
            date_of_birth=existing.pii.date_of_birth,
            contact_details=existing.pii.contact_details,
            anchor_status=existing.anchor_status,
            creation_date=existing.creation_date,
            revision=existing.revision,
            pseudonymized_at=existing.pseudonymized_at,
            last_processed_command_id=existing.last_processed_command_id,
            last_processed_client_request_id=existing.last_processed_client_request_id,
            crypto_key_id=existing.crypto_key_id,
        )

    async def update(self, anchor: IdentityAnchor) -> None:
        assert str(anchor.internal_id) in self.rows
        # Persist a fresh hydrated copy (mirrors the SQL UPDATE semantics
        # — we don't keep the events queue in the stored row).
        self.rows[str(anchor.internal_id)] = IdentityAnchor.hydrate(
            internal_id=str(anchor.internal_id),
            last_name=anchor.pii.last_name,
            first_name=anchor.pii.first_name,
            date_of_birth=anchor.pii.date_of_birth,
            contact_details=anchor.pii.contact_details,
            anchor_status=anchor.anchor_status,
            creation_date=anchor.creation_date,
            revision=anchor.revision,
            pseudonymized_at=anchor.pseudonymized_at,
            last_processed_command_id=anchor.last_processed_command_id,
            last_processed_client_request_id=anchor.last_processed_client_request_id,
            crypto_key_id=anchor.crypto_key_id,
        )


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


class _InMemoryCryptoKeyRepo:
    """In-memory DEK ledger. Counts ``shred`` invocations so we can assert
    that crypto-shred runs at most once per command_id (idempotency
    post-condition).
    """

    def __init__(self) -> None:
        self.keys: set[str] = set()
        self.shred_calls: list[str] = []

    async def provision(self, *, crypto_key_id: str) -> None:
        self.keys.add(crypto_key_id)

    async def shred(self, *, crypto_key_id: str) -> None:
        self.shred_calls.append(crypto_key_id)
        self.keys.discard(crypto_key_id)

    async def exists(self, *, crypto_key_id: str) -> bool:
        return crypto_key_id in self.keys


class _InMemoryUoW(UnitOfWork):
    def __init__(self, anchors, outbox, idem, crypto_keys):
        self.anchors = anchors
        self.outbox = outbox
        self.idempotency = idem
        self.crypto_keys = crypto_keys
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
        self.crypto_keys = _InMemoryCryptoKeyRepo()
        self.uows: list[_InMemoryUoW] = []

    def __call__(self) -> _InMemoryUoW:
        u = _InMemoryUoW(self.anchors, self.outbox, self.idem, self.crypto_keys)
        self.uows.append(u)
        return u


# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def validators(schemas_dir):
    return build_validators_bundle(schemas_dir)


@pytest.fixture
def factory():
    return _InMemoryUoWFactory()


@pytest.fixture
def handler(factory, validators):
    return PseudonymiseAnchorHandler(
        uow_factory=factory, rvt_validator=validators.rvt
    )


def _actor() -> Actor:
    return Actor(kind="human", subject=_uuidv7())


def _seed_anchor(
    factory: _InMemoryUoWFactory,
    *,
    anchor_status: str = "ACTIVE",
    revision: int = 1,
    crypto_key_id: str | None = None,
) -> tuple[IdentityAnchor, str]:
    crypto_key = crypto_key_id or _uuidv7()
    anchor = IdentityAnchor.hydrate(
        internal_id=_INTERNAL_ID,
        last_name="Dupont",
        first_name="Marie",
        date_of_birth=date(1985, 6, 21),
        contact_details=ContactDetails(
            email="marie.dupont@example.org",
            phone="+33 1 23 45 67 89",
        ),
        anchor_status=anchor_status,  # type: ignore[arg-type]
        creation_date=date(2024, 1, 15),
        revision=revision,
        crypto_key_id=crypto_key,
    )
    factory.anchors.rows[str(anchor.internal_id)] = anchor
    factory.crypto_keys.keys.add(crypto_key)
    return anchor, crypto_key


def _cmd(
    cid: str,
    *,
    right_exercise_id: str | None = None,
    reason: str = "GDPR_ART17_REQUEST",
    internal_id: str = _INTERNAL_ID,
) -> PseudonymiseAnchorCommandDto:
    return PseudonymiseAnchorCommandDto(
        internal_id=internal_id,
        command_id=cid,
        right_exercise_id=right_exercise_id or _uuidv7(),
        reason=reason,  # type: ignore[arg-type]
        comment=None,
        actor=_actor(),
    )


# ─── Tests — happy path ────────────────────────────────────────────────


class TestPseudonymiseHandlerHappyPath:
    async def test_active_to_pseudonymised_returns_200(self, handler, factory):
        _seed_anchor(factory, revision=3)
        result = await handler.handle(_cmd(_uuidv7()))
        assert result.http_status == 200
        assert result.idempotent_replay is False
        assert result.error_code is None
        assert result.anchor.anchor_status == "PSEUDONYMISED"
        assert result.anchor.last_name is None
        assert result.anchor.first_name is None
        assert result.anchor.date_of_birth is None
        assert result.anchor.contact_details is None
        assert result.anchor.pseudonymized_at is not None
        assert result.anchor.revision == 4  # N+1

    async def test_archived_to_pseudonymised_returns_200(self, handler, factory):
        """INV.BEN.006 — PSEUDONYMISE accepts from ARCHIVED as well as ACTIVE."""
        _seed_anchor(factory, anchor_status="ARCHIVED", revision=2)
        result = await handler.handle(_cmd(_uuidv7()))
        assert result.http_status == 200
        assert result.anchor.anchor_status == "PSEUDONYMISED"
        assert result.anchor.revision == 3

    async def test_writes_exactly_one_outbox_row(self, handler, factory):
        _seed_anchor(factory)
        await handler.handle(_cmd(_uuidv7()))
        assert len(factory.outbox.rows) == 1
        row = factory.outbox.rows[0]
        assert row["exchange"] == "sup.002.ben-events"
        assert row["routing_key"] == (
            "BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED."
            "BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED"
        )

    async def test_outbox_payload_carries_pseudonymised_transition_kind(
        self, handler, factory,
    ):
        _seed_anchor(factory)
        right_id = _uuidv7()
        await handler.handle(_cmd(_uuidv7(), right_exercise_id=right_id))
        payload = factory.outbox.rows[0]["payload"]
        assert payload["transition_kind"] == "PSEUDONYMISED"
        assert payload["anchor_status"] == "PSEUDONYMISED"
        assert payload["last_name"] is None
        assert payload["first_name"] is None
        assert payload["date_of_birth"] is None
        assert payload["contact_details"] is None
        assert payload["right_exercise_id"] == right_id
        assert payload["pseudonymized_at"] is not None
        assert payload["revision"] == 2

    async def test_dek_is_shredded_in_same_transaction(self, handler, factory):
        """The crypto-shred observable post-condition: the per-anchor DEK
        row is gone after a successful pseudonymisation."""
        _, crypto_key_id = _seed_anchor(factory)
        assert await factory.crypto_keys.exists(crypto_key_id=crypto_key_id) is True
        await handler.handle(_cmd(_uuidv7()))
        assert await factory.crypto_keys.exists(crypto_key_id=crypto_key_id) is False
        assert factory.crypto_keys.shred_calls == [crypto_key_id]

    async def test_anchor_row_has_pii_nulled_and_key_severed(self, handler, factory):
        _, _ = _seed_anchor(factory)
        await handler.handle(_cmd(_uuidv7()))
        row = factory.anchors.rows[_INTERNAL_ID]
        assert row.pii.last_name is None
        assert row.pii.first_name is None
        assert row.pii.date_of_birth is None
        assert row.pii.contact_details is None
        assert row.crypto_key_id is None
        assert row.anchor_status == "PSEUDONYMISED"

    async def test_internal_id_is_preserved_after_pseudonymisation(
        self, handler, factory,
    ):
        """INV.BEN.002 — even after pseudonymisation the internal_id is unchanged."""
        _seed_anchor(factory)
        result = await handler.handle(_cmd(_uuidv7()))
        assert result.anchor.internal_id == _INTERNAL_ID

    async def test_outbox_payload_validates_against_rvt_schema(
        self, handler, factory, validators,
    ):
        """The if/then PSEUDONYMISED branch of the canonical RVT schema is
        exercised — null PII, status PSEUDONYMISED, pseudonymized_at and
        right_exercise_id required.
        """
        _seed_anchor(factory)
        await handler.handle(_cmd(_uuidv7()))
        payload = factory.outbox.rows[0]["payload"]
        validators.rvt.validate_payload(payload)


# ─── Idempotency (INV.BEN.008) ─────────────────────────────────────────


class TestPseudonymiseHandlerIdempotency:
    async def test_duplicate_command_id_returns_command_already_processed(
        self, handler, factory,
    ):
        _seed_anchor(factory)
        cid = _uuidv7()
        first = await handler.handle(_cmd(cid))
        second = await handler.handle(_cmd(cid))

        assert first.idempotent_replay is False
        assert second.idempotent_replay is True
        assert second.error_code == "COMMAND_ALREADY_PROCESSED"
        assert second.http_status == 200
        # Same anchor snapshot returned.
        assert second.anchor.internal_id == first.anchor.internal_id
        assert second.anchor.revision == first.anchor.revision

    async def test_duplicate_command_id_does_not_write_second_outbox_row(
        self, handler, factory,
    ):
        _seed_anchor(factory)
        cid = _uuidv7()
        await handler.handle(_cmd(cid))
        await handler.handle(_cmd(cid))
        assert len(factory.outbox.rows) == 1

    async def test_duplicate_command_id_does_not_re_shred(
        self, handler, factory,
    ):
        """The crypto-shred runs exactly once across a duplicate command_id —
        the second call is short-circuited by the idempotency table BEFORE
        ``crypto_keys.shred(...)`` would ever be invoked."""
        _, crypto_key_id = _seed_anchor(factory)
        cid = _uuidv7()
        await handler.handle(_cmd(cid))
        await handler.handle(_cmd(cid))
        # Exactly one shred call across both invocations.
        assert factory.crypto_keys.shred_calls == [crypto_key_id]

    async def test_idempotency_row_carries_pseudonymise_scope(
        self, handler, factory,
    ):
        _seed_anchor(factory)
        cid = _uuidv7()
        await handler.handle(_cmd(cid))
        assert (IDEMPOTENCY_SCOPE_PSEUDONYMISE, cid) in factory.idem.rows


# ─── INV.BEN.006 — terminal-state guard ────────────────────────────────


class TestPseudonymiseHandlerTerminalState:
    async def test_pseudonymised_anchor_rejects_with_409(self, handler, factory):
        """Manually seed an anchor already in PSEUDONYMISED status — the
        handler must surface AnchorAlreadyPseudonymised → 409."""
        anchor = IdentityAnchor.hydrate(
            internal_id=_INTERNAL_ID,
            last_name=None,
            first_name=None,
            date_of_birth=None,
            contact_details=None,
            anchor_status="PSEUDONYMISED",
            creation_date=date(2024, 1, 15),
            revision=4,
            pseudonymized_at=datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc),
            crypto_key_id=None,  # already severed
        )
        factory.anchors.rows[_INTERNAL_ID] = anchor

        with pytest.raises(AnchorAlreadyPseudonymised) as exc_info:
            await handler.handle(_cmd(_uuidv7()))
        assert exc_info.value.code == "ANCHOR_ALREADY_PSEUDONYMISED"

        # No outbox row was written; no DEK was shredded (there's none
        # left to shred, but also no spurious call attempted).
        assert factory.outbox.rows == []
        assert factory.crypto_keys.shred_calls == []


# ─── ANCHOR_NOT_FOUND ──────────────────────────────────────────────────


class TestPseudonymiseHandlerNotFound:
    async def test_missing_anchor_raises_anchor_not_found(self, handler, factory):
        with pytest.raises(AnchorNotFound) as exc_info:
            await handler.handle(_cmd(_uuidv7()))
        assert exc_info.value.code == "ANCHOR_NOT_FOUND"
        assert factory.outbox.rows == []
        assert factory.crypto_keys.shred_calls == []
