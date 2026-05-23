"""Application-layer tests for ArchiveAnchorHandler / RestoreAnchorHandler
(TASK-004) — uses in-memory ports so the test runs without Postgres or
Rabbit.

Covers:
  * fresh archive / restore → 200, one outbox row, one idempotency row,
    bumped revision, correct transition_kind + anchor_status
  * idempotent replay → 200, COMMAND_ALREADY_PROCESSED, no second outbox /
    idempotency row
  * state-machine guards bubble up as DomainError
  * ARCHIVE→RESTORE round-trip through the handlers (status + PII continuity)
  * RVT payload validates against the canonical schema with
    transition_kind=ARCHIVED / RESTORED
"""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

import pytest

from reliever_beneficiary_anchor.application.dto import (
    ArchiveAnchorCommandDto,
    RestoreAnchorCommandDto,
)
from reliever_beneficiary_anchor.application.handlers import (
    IDEMPOTENCY_SCOPE_ARCHIVE,
    IDEMPOTENCY_SCOPE_RESTORE,
    ArchiveAnchorHandler,
    RestoreAnchorHandler,
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
    AnchorAlreadyArchived,
    AnchorNotArchived,
    AnchorNotFound,
    AnchorPseudonymised,
)
from reliever_beneficiary_anchor.domain.value_objects import Actor, ContactDetails
from reliever_beneficiary_anchor.infrastructure.schema_validation.loader import (
    build_validators_bundle,
)

_INTERNAL_ID = "018f8e10-9999-7000-8000-00000000aaaa"


# ─── In-memory ports (mirror test_update_handler.py) ───────────────────


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
        )

    async def update(self, anchor: IdentityAnchor) -> None:
        assert str(anchor.internal_id) in self.rows
        self.rows[str(anchor.internal_id)] = anchor


class _InMemoryOutboxRepo(OutboxRepository):
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def append(self, **kw: Any) -> None:
        self.rows.append(kw)


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

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class _InMemoryUoWFactory(UnitOfWorkFactory):
    def __init__(self):
        self.anchors = _InMemoryAnchorRepo()
        self.outbox = _InMemoryOutboxRepo()
        self.idem = _InMemoryIdempotencyRepo()

    def __call__(self) -> _InMemoryUoW:
        return _InMemoryUoW(self.anchors, self.outbox, self.idem)


# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def validators(schemas_dir):
    return build_validators_bundle(schemas_dir)


@pytest.fixture
def factory():
    return _InMemoryUoWFactory()


@pytest.fixture
def archive_handler(factory, validators):
    return ArchiveAnchorHandler(uow_factory=factory, rvt_validator=validators.rvt)


@pytest.fixture
def restore_handler(factory, validators):
    return RestoreAnchorHandler(uow_factory=factory, rvt_validator=validators.rvt)


def _actor() -> Actor:
    return Actor(kind="human", subject="018f8e10-2222-7000-8000-0000000000aa")


def _seed(
    factory: _InMemoryUoWFactory,
    *,
    anchor_status: str = "ACTIVE",
    revision: int = 1,
    contact: ContactDetails | None = None,
) -> IdentityAnchor:
    anchor = IdentityAnchor.hydrate(
        internal_id=_INTERNAL_ID,
        last_name="Dupont",
        first_name="Marie",
        date_of_birth=date(1985, 6, 21),
        contact_details=contact,
        anchor_status=anchor_status,  # type: ignore[arg-type]
        creation_date=date(2024, 1, 15),
        revision=revision,
    )
    factory.anchors.rows[str(anchor.internal_id)] = anchor
    return anchor


def _archive_cmd(cid: str, *, reason: str = "PROGRAMME_EXIT_SUCCESS") -> ArchiveAnchorCommandDto:
    return ArchiveAnchorCommandDto(
        internal_id=_INTERNAL_ID, command_id=cid, reason=reason, comment=None, actor=_actor()
    )


def _restore_cmd(cid: str, *, reason: str = "ARCHIVED_IN_ERROR") -> RestoreAnchorCommandDto:
    return RestoreAnchorCommandDto(
        internal_id=_INTERNAL_ID, command_id=cid, reason=reason, comment=None, actor=_actor()
    )


# ─── ARCHIVE ───────────────────────────────────────────────────────────


class TestArchiveHandlerFreshApply:
    async def test_returns_200_bumped_revision_archived_status(self, archive_handler, factory):
        _seed(factory, revision=3)
        result = await archive_handler.handle(
            _archive_cmd("018f8e10-cccc-7000-8000-000000000001")
        )
        assert result.http_status == 200
        assert result.idempotent_replay is False
        assert result.anchor.revision == 4
        assert result.anchor.anchor_status == "ARCHIVED"

    async def test_one_outbox_row_with_transition_kind_archived(self, archive_handler, factory):
        _seed(factory)
        await archive_handler.handle(_archive_cmd("018f8e10-cccc-7000-8000-000000000002"))
        assert len(factory.outbox.rows) == 1
        payload = factory.outbox.rows[0]["payload"]
        assert payload["transition_kind"] == "ARCHIVED"
        assert payload["anchor_status"] == "ARCHIVED"
        assert payload["revision"] == 2
        assert factory.outbox.rows[0]["routing_key"] == (
            "BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED."
            "BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED"
        )

    async def test_outbox_payload_validates_against_rvt_schema(
        self, archive_handler, factory, validators
    ):
        _seed(factory)
        await archive_handler.handle(_archive_cmd("018f8e10-cccc-7000-8000-000000000003"))
        validators.rvt.validate_payload(factory.outbox.rows[0]["payload"])

    async def test_idempotency_row_scoped_archive(self, archive_handler, factory):
        _seed(factory)
        cid = "018f8e10-cccc-7000-8000-000000000004"
        await archive_handler.handle(_archive_cmd(cid))
        assert (IDEMPOTENCY_SCOPE_ARCHIVE, cid) in factory.idem.rows

    async def test_pii_unchanged(self, archive_handler, factory):
        _seed(factory, contact=ContactDetails(email="marie@example.org"))
        await archive_handler.handle(_archive_cmd("018f8e10-cccc-7000-8000-000000000005"))
        stored = factory.anchors.rows[_INTERNAL_ID]
        assert stored.pii.last_name == "Dupont"
        assert stored.pii.contact_details is not None
        assert stored.pii.contact_details.email == "marie@example.org"


class TestArchiveHandlerIdempotency:
    async def test_replay_returns_command_already_processed(self, archive_handler, factory):
        _seed(factory)
        cid = "018f8e10-cccc-7000-8000-000000000010"
        first = await archive_handler.handle(_archive_cmd(cid))
        second = await archive_handler.handle(_archive_cmd(cid))
        assert second.idempotent_replay is True
        assert second.error_code == "COMMAND_ALREADY_PROCESSED"
        assert second.anchor.revision == first.anchor.revision

    async def test_replay_writes_no_second_outbox_row(self, archive_handler, factory):
        _seed(factory)
        cid = "018f8e10-cccc-7000-8000-000000000011"
        await archive_handler.handle(_archive_cmd(cid))
        await archive_handler.handle(_archive_cmd(cid))
        assert len(factory.outbox.rows) == 1


class TestArchiveHandlerGuards:
    async def test_not_found(self, archive_handler):
        with pytest.raises(AnchorNotFound):
            await archive_handler.handle(_archive_cmd("018f8e10-cccc-7000-8000-000000000020"))

    async def test_already_archived(self, archive_handler, factory):
        _seed(factory, anchor_status="ARCHIVED")
        with pytest.raises(AnchorAlreadyArchived):
            await archive_handler.handle(_archive_cmd("018f8e10-cccc-7000-8000-000000000021"))

    async def test_pseudonymised(self, archive_handler, factory):
        _seed(factory, anchor_status="PSEUDONYMISED")
        with pytest.raises(AnchorPseudonymised):
            await archive_handler.handle(_archive_cmd("018f8e10-cccc-7000-8000-000000000022"))


# ─── RESTORE ───────────────────────────────────────────────────────────


class TestRestoreHandlerFreshApply:
    async def test_returns_200_active_status(self, restore_handler, factory):
        _seed(factory, anchor_status="ARCHIVED", revision=5)
        result = await restore_handler.handle(
            _restore_cmd("018f8e10-dddd-7000-8000-000000000001")
        )
        assert result.http_status == 200
        assert result.anchor.anchor_status == "ACTIVE"
        assert result.anchor.revision == 6

    async def test_one_outbox_row_transition_kind_restored(self, restore_handler, factory):
        _seed(factory, anchor_status="ARCHIVED")
        await restore_handler.handle(_restore_cmd("018f8e10-dddd-7000-8000-000000000002"))
        payload = factory.outbox.rows[0]["payload"]
        assert payload["transition_kind"] == "RESTORED"
        assert payload["anchor_status"] == "ACTIVE"

    async def test_outbox_payload_validates(self, restore_handler, factory, validators):
        _seed(factory, anchor_status="ARCHIVED")
        await restore_handler.handle(_restore_cmd("018f8e10-dddd-7000-8000-000000000003"))
        validators.rvt.validate_payload(factory.outbox.rows[0]["payload"])

    async def test_idempotency_row_scoped_restore(self, restore_handler, factory):
        _seed(factory, anchor_status="ARCHIVED")
        cid = "018f8e10-dddd-7000-8000-000000000004"
        await restore_handler.handle(_restore_cmd(cid))
        assert (IDEMPOTENCY_SCOPE_RESTORE, cid) in factory.idem.rows


class TestRestoreHandlerIdempotency:
    async def test_replay_returns_command_already_processed(self, restore_handler, factory):
        _seed(factory, anchor_status="ARCHIVED")
        cid = "018f8e10-dddd-7000-8000-000000000010"
        await restore_handler.handle(_restore_cmd(cid))
        second = await restore_handler.handle(_restore_cmd(cid))
        assert second.idempotent_replay is True
        assert second.error_code == "COMMAND_ALREADY_PROCESSED"
        assert len(factory.outbox.rows) == 1


class TestRestoreHandlerGuards:
    async def test_not_found(self, restore_handler):
        with pytest.raises(AnchorNotFound):
            await restore_handler.handle(_restore_cmd("018f8e10-dddd-7000-8000-000000000020"))

    async def test_not_archived_when_active(self, restore_handler, factory):
        _seed(factory, anchor_status="ACTIVE")
        with pytest.raises(AnchorNotArchived):
            await restore_handler.handle(_restore_cmd("018f8e10-dddd-7000-8000-000000000021"))

    async def test_pseudonymised(self, restore_handler, factory):
        _seed(factory, anchor_status="PSEUDONYMISED")
        with pytest.raises(AnchorPseudonymised):
            await restore_handler.handle(_restore_cmd("018f8e10-dddd-7000-8000-000000000022"))


# ─── ROUND-TRIP ────────────────────────────────────────────────────────


class TestArchiveRestoreRoundTrip:
    async def test_active_archive_restore_continuity(
        self, archive_handler, restore_handler, factory
    ):
        _seed(factory, revision=1, contact=ContactDetails(email="marie@example.org"))
        ar = await archive_handler.handle(_archive_cmd("018f8e10-eeee-7000-8000-000000000001"))
        assert ar.anchor.anchor_status == "ARCHIVED"
        assert ar.anchor.revision == 2

        rr = await restore_handler.handle(_restore_cmd("018f8e10-eeee-7000-8000-000000000002"))
        assert rr.anchor.anchor_status == "ACTIVE"
        assert rr.anchor.revision == 3

        # Two distinct outbox rows: ARCHIVED then RESTORED.
        kinds = [r["payload"]["transition_kind"] for r in factory.outbox.rows]
        assert kinds == ["ARCHIVED", "RESTORED"]

        # PII unchanged throughout (INV.BEN.002).
        stored = factory.anchors.rows[_INTERNAL_ID]
        assert stored.pii.last_name == "Dupont"
        assert stored.pii.contact_details is not None
        assert stored.pii.contact_details.email == "marie@example.org"
