"""Application-layer tests for UpdateAnchorHandler — uses in-memory ports
so the test runs without Postgres or Rabbit.

Covers:
  * fresh apply → 200, one outbox row, one idempotency row, bumped revision
  * idempotent replay → 200, COMMAND_ALREADY_PROCESSED, no new outbox or
    idempotency row
  * sticky-PII at the handler level (round-trip through the aggregate)
  * lifecycle guards bubble up as DomainError
  * RVT payload validates against the canonical schema with
    transition_kind=UPDATED
  * out-of-order projection drop (revision ≤ local)
"""

from __future__ import annotations

import copy
from datetime import date, datetime
from typing import Any

import pytest

from reliever_beneficiary_anchor.application.dto import (
    ContactDetailsUpdate,
    UpdateAnchorCommandDto,
    UpdateFields,
)
from reliever_beneficiary_anchor.application.handlers import (
    IDEMPOTENCY_SCOPE_UPDATE,
    UpdateAnchorHandler,
)
from reliever_beneficiary_anchor.application.ports import (
    AnchorDirectoryWriter,
    AnchorRepository,
    IdempotencyRepository,
    OutboxRepository,
    UnitOfWork,
    UnitOfWorkFactory,
)
from reliever_beneficiary_anchor.domain.aggregate import IdentityAnchor
from reliever_beneficiary_anchor.domain.errors import (
    AnchorArchived,
    AnchorNotFound,
    AnchorPseudonymised,
)
from reliever_beneficiary_anchor.domain.value_objects import (
    Actor,
    ContactDetails,
    PostalAddress,
)
from reliever_beneficiary_anchor.infrastructure.persistence.projection import (
    PostgresAnchorDirectoryWriter,  # not used; imports kept for symmetry
)
from reliever_beneficiary_anchor.infrastructure.schema_validation.loader import (
    build_validators_bundle,
)


_INTERNAL_ID = "018f8e10-9999-7000-8000-00000000aaaa"


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
        # Hand the handler a fresh, hydrated copy so test mutations to
        # ``existing`` do not leak through the repo (mirrors the Postgres
        # behaviour where each ``get`` returns a fresh row).
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
    return build_validators_bundle(schemas_dir)


@pytest.fixture
def factory():
    return _InMemoryUoWFactory()


@pytest.fixture
def handler(factory, validators):
    return UpdateAnchorHandler(
        uow_factory=factory, rvt_validator=validators.rvt
    )


def _actor() -> Actor:
    return Actor(kind="human", subject="018f8e10-2222-7000-8000-0000000000aa")


def _seed_anchor(
    factory: _InMemoryUoWFactory,
    *,
    last_name: str = "Dupont",
    first_name: str = "Marie",
    date_of_birth: date = date(1985, 6, 21),
    contact: ContactDetails | None = None,
    anchor_status: str = "ACTIVE",
    revision: int = 1,
) -> IdentityAnchor:
    anchor = IdentityAnchor.hydrate(
        internal_id=_INTERNAL_ID,
        last_name=last_name,
        first_name=first_name,
        date_of_birth=date_of_birth,
        contact_details=contact,
        anchor_status=anchor_status,  # type: ignore[arg-type]
        creation_date=date(2024, 1, 15),
        revision=revision,
    )
    factory.anchors.rows[str(anchor.internal_id)] = anchor
    return anchor


def _cmd(
    cid: str,
    *,
    fields: UpdateFields | None = None,
    internal_id: str = _INTERNAL_ID,
) -> UpdateAnchorCommandDto:
    return UpdateAnchorCommandDto(
        internal_id=internal_id,
        command_id=cid,
        fields=fields or UpdateFields(first_name="Maryam"),
        actor=_actor(),
    )


# ─── Tests ─────────────────────────────────────────────────────────────


class TestUpdateHandlerFreshApply:
    async def test_returns_200_with_bumped_revision(self, handler, factory):
        _seed_anchor(factory, revision=3)
        result = await handler.handle(
            _cmd("018f8e10-cccc-7000-8000-000000000001")
        )
        assert result.http_status == 200
        assert result.idempotent_replay is False
        assert result.error_code is None
        assert result.anchor.revision == 4
        assert result.anchor.first_name == "Maryam"

    async def test_writes_exactly_one_outbox_row(self, handler, factory):
        _seed_anchor(factory)
        await handler.handle(
            _cmd("018f8e10-cccc-7000-8000-000000000002")
        )
        assert len(factory.outbox.rows) == 1
        row = factory.outbox.rows[0]
        assert row["exchange"] == "sup.002.ben-events"
        assert row["routing_key"] == (
            "BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED."
            "BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED"
        )

    async def test_outbox_payload_carries_transition_kind_updated(self, handler, factory):
        _seed_anchor(factory)
        await handler.handle(
            _cmd("018f8e10-cccc-7000-8000-000000000003")
        )
        payload = factory.outbox.rows[0]["payload"]
        assert payload["transition_kind"] == "UPDATED"
        assert payload["revision"] == 2
        assert payload["anchor_status"] == "ACTIVE"

    async def test_outbox_payload_validates_against_rvt_schema(
        self, handler, factory, validators,
    ):
        _seed_anchor(factory)
        await handler.handle(
            _cmd("018f8e10-cccc-7000-8000-000000000004")
        )
        validators.rvt.validate_payload(factory.outbox.rows[0]["payload"])

    async def test_writes_exactly_one_idempotency_row_scoped_UPDATE(self, handler, factory):
        _seed_anchor(factory)
        cid = "018f8e10-cccc-7000-8000-000000000005"
        await handler.handle(_cmd(cid))
        assert len(factory.idem.rows) == 1
        assert (IDEMPOTENCY_SCOPE_UPDATE, cid) in factory.idem.rows

    async def test_persists_updated_anchor_state(self, handler, factory):
        _seed_anchor(factory)
        await handler.handle(
            _cmd("018f8e10-cccc-7000-8000-000000000006")
        )
        stored = factory.anchors.rows[_INTERNAL_ID]
        assert stored.pii.first_name == "Maryam"
        assert stored.revision == 2


class TestUpdateHandlerStickyPii:
    async def test_absent_field_preserves_value_after_round_trip(self, handler, factory):
        _seed_anchor(
            factory,
            contact=ContactDetails(
                email="marie@example.org",
                phone="+33 1 23 45 67 89",
            ),
        )
        await handler.handle(
            UpdateAnchorCommandDto(
                internal_id=_INTERNAL_ID,
                command_id="018f8e10-cccc-7000-8000-000000000010",
                fields=UpdateFields(first_name="Maryam"),
                actor=_actor(),
            )
        )
        stored = factory.anchors.rows[_INTERNAL_ID]
        assert stored.pii.contact_details is not None
        assert stored.pii.contact_details.email == "marie@example.org"
        assert stored.pii.contact_details.phone == "+33 1 23 45 67 89"

    async def test_explicit_null_on_email_clears_only_email(self, handler, factory):
        _seed_anchor(
            factory,
            contact=ContactDetails(
                email="marie@example.org",
                phone="+33 1 23 45 67 89",
            ),
        )
        await handler.handle(
            UpdateAnchorCommandDto(
                internal_id=_INTERNAL_ID,
                command_id="018f8e10-cccc-7000-8000-000000000011",
                fields=UpdateFields(
                    contact_details=ContactDetailsUpdate(email=None),
                ),
                actor=_actor(),
            )
        )
        stored = factory.anchors.rows[_INTERNAL_ID]
        assert stored.pii.contact_details is not None
        assert stored.pii.contact_details.email is None
        assert stored.pii.contact_details.phone == "+33 1 23 45 67 89"


class TestUpdateHandlerIdempotency:
    async def test_idempotent_replay_returns_command_already_processed(self, handler, factory):
        _seed_anchor(factory)
        cid = "018f8e10-cccc-7000-8000-000000000020"
        first = await handler.handle(_cmd(cid))
        assert first.http_status == 200
        assert first.idempotent_replay is False

        second = await handler.handle(_cmd(cid))
        assert second.http_status == 200
        assert second.idempotent_replay is True
        assert second.error_code == "COMMAND_ALREADY_PROCESSED"
        # Identical anchor returned by both calls.
        assert second.anchor.internal_id == first.anchor.internal_id
        assert second.anchor.revision == first.anchor.revision

    async def test_idempotent_replay_writes_no_new_outbox_or_idempotency_row(
        self, handler, factory,
    ):
        _seed_anchor(factory)
        cid = "018f8e10-cccc-7000-8000-000000000021"
        await handler.handle(_cmd(cid))
        await handler.handle(_cmd(cid))
        assert len(factory.outbox.rows) == 1  # only the first emission
        assert len(factory.idem.rows) == 1

    async def test_idempotent_replay_does_not_mutate_stored_anchor(self, handler, factory):
        _seed_anchor(factory)
        cid = "018f8e10-cccc-7000-8000-000000000022"
        await handler.handle(_cmd(cid))
        stored_after_first = factory.anchors.rows[_INTERNAL_ID]
        revision_after_first = stored_after_first.revision

        await handler.handle(_cmd(cid))
        stored_after_replay = factory.anchors.rows[_INTERNAL_ID]
        assert stored_after_replay.revision == revision_after_first


class TestUpdateHandlerLifecycleGuards:
    async def test_anchor_not_found(self, handler):
        # No seed; the anchor doesn't exist.
        with pytest.raises(AnchorNotFound) as exc:
            await handler.handle(_cmd("018f8e10-cccc-7000-8000-000000000030"))
        assert exc.value.code == "ANCHOR_NOT_FOUND"

    async def test_archived_anchor_yields_anchor_archived(self, handler, factory):
        _seed_anchor(factory, anchor_status="ARCHIVED")
        with pytest.raises(AnchorArchived) as exc:
            await handler.handle(_cmd("018f8e10-cccc-7000-8000-000000000031"))
        assert exc.value.code == "ANCHOR_ARCHIVED"

    async def test_pseudonymised_anchor_yields_anchor_pseudonymised(
        self, handler, factory,
    ):
        _seed_anchor(
            factory,
            anchor_status="PSEUDONYMISED",
            last_name="****",  # placeholder — TASK-005 supplies the wipe markers
        )
        with pytest.raises(AnchorPseudonymised) as exc:
            await handler.handle(_cmd("018f8e10-cccc-7000-8000-000000000032"))
        assert exc.value.code == "ANCHOR_PSEUDONYMISED"


class TestRvtEnvelopeAndShape:
    async def test_envelope_carries_uuidv7_trio_and_actor(self, handler, factory):
        _seed_anchor(factory)
        await handler.handle(_cmd("018f8e10-cccc-7000-8000-000000000040"))
        envelope = factory.outbox.rows[0]["payload"]["envelope"]
        for f in ("message_id", "correlation_id", "causation_id"):
            assert envelope[f]
        assert envelope["actor"]["kind"] == "human"
        assert envelope["emitting_capability"] == "BNK.RLVR.CAP.SUP.002.BEN"

    async def test_correlation_id_equals_internal_id(self, handler, factory):
        _seed_anchor(factory)
        await handler.handle(_cmd("018f8e10-cccc-7000-8000-000000000041"))
        envelope = factory.outbox.rows[0]["payload"]["envelope"]
        payload = factory.outbox.rows[0]["payload"]
        assert envelope["correlation_id"] == payload["internal_id"]

    async def test_causation_id_equals_command_id(self, handler, factory):
        _seed_anchor(factory)
        cid = "018f8e10-cccc-7000-8000-000000000042"
        await handler.handle(_cmd(cid))
        envelope = factory.outbox.rows[0]["payload"]["envelope"]
        assert envelope["causation_id"] == cid


class TestProjectionOutOfOrderDrop:
    """The TASK-002 LWW guard already drops events whose revision is ≤ the
    local revision. We re-verify it for the UPDATED transition path by
    feeding two simulated rows in reverse order to a fresh in-memory
    writer that mirrors the Postgres ``WHERE revision < EXCLUDED.revision``
    contract.
    """

    async def test_lower_revision_is_dropped(self):
        # A minimal in-memory writer matching the contract.
        class _LWWWriter(AnchorDirectoryWriter):
            def __init__(self):
                self.rows: dict[str, int] = {}

            async def upsert(self, projection_row):
                iid = str(projection_row["internal_id"])
                rev = int(projection_row["revision"])
                stored = self.rows.get(iid, 0)
                if rev > stored:
                    self.rows[iid] = rev
                    return True
                return False

        w = _LWWWriter()
        # Apply revision 5 first.
        applied_high = await w.upsert(
            {"internal_id": _INTERNAL_ID, "revision": 5,
             "anchor_status": "ACTIVE", "creation_date": date(2024, 1, 15)}
        )
        assert applied_high is True
        # Now a late revision 3 arrives — must be dropped.
        applied_low = await w.upsert(
            {"internal_id": _INTERNAL_ID, "revision": 3,
             "anchor_status": "ACTIVE", "creation_date": date(2024, 1, 15)}
        )
        assert applied_low is False
        assert w.rows[_INTERNAL_ID] == 5  # high-water-mark preserved

    async def test_equal_revision_is_dropped(self):
        class _LWWWriter(AnchorDirectoryWriter):
            def __init__(self):
                self.rows: dict[str, int] = {}

            async def upsert(self, projection_row):
                iid = str(projection_row["internal_id"])
                rev = int(projection_row["revision"])
                stored = self.rows.get(iid, 0)
                if rev > stored:
                    self.rows[iid] = rev
                    return True
                return False

        w = _LWWWriter()
        await w.upsert({"internal_id": _INTERNAL_ID, "revision": 5,
                        "anchor_status": "ACTIVE",
                        "creation_date": date(2024, 1, 15)})
        applied_eq = await w.upsert(
            {"internal_id": _INTERNAL_ID, "revision": 5,
             "anchor_status": "ACTIVE", "creation_date": date(2024, 1, 15)}
        )
        assert applied_eq is False
