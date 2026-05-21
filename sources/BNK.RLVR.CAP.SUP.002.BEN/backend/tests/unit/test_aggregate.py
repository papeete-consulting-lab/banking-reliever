"""Domain-layer unit tests — pure Python, no I/O."""

from __future__ import annotations

import re
from datetime import date

import pytest

from reliever_beneficiary_anchor.domain.aggregate import IdentityAnchor
from reliever_beneficiary_anchor.domain.errors import IdentityFieldsMissing
from reliever_beneficiary_anchor.domain.value_objects import (
    Actor,
    ClientRequestId,
    ContactDetails,
    InternalId,
)

_UUIDV7 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def _crid() -> ClientRequestId:
    # A fixed example UUIDv7 — RFC-9562 §5.7.
    return ClientRequestId("018f8e10-1111-7000-8000-000000000001")


def _actor() -> Actor:
    return Actor(kind="human", subject="018f8e10-2222-7000-8000-000000000001")


class TestIdentityAnchorMint:
    def test_mints_uuidv7_internal_id(self):
        anchor = IdentityAnchor.mint(
            client_request_id=_crid(),
            last_name="Doe",
            first_name="Jane",
            date_of_birth=date(1990, 1, 15),
            contact_details=None,
            actor=_actor(),
        )
        assert _UUIDV7.match(str(anchor.internal_id))

    def test_status_revision_and_creation_date(self):
        anchor = IdentityAnchor.mint(
            client_request_id=_crid(),
            last_name="Doe",
            first_name="Jane",
            date_of_birth=date(1990, 1, 15),
            contact_details=None,
            actor=_actor(),
        )
        assert anchor.anchor_status == "ACTIVE"
        assert anchor.revision == 1
        assert anchor.last_processed_client_request_id == str(_crid())

    def test_emits_exactly_one_minted_event(self):
        anchor = IdentityAnchor.mint(
            client_request_id=_crid(),
            last_name="Doe",
            first_name="Jane",
            date_of_birth=date(1990, 1, 15),
            contact_details=ContactDetails(email="jane@example.org"),
            actor=_actor(),
        )
        events = anchor.pull_pending_events()
        assert len(events) == 1
        evt = events[0]
        assert evt.transition_kind == "MINTED"
        assert evt.revision == 1
        assert evt.last_name == "Doe"
        assert evt.first_name == "Jane"
        assert evt.date_of_birth == date(1990, 1, 15)
        assert evt.command_id == str(_crid())

    @pytest.mark.parametrize(
        "last,first,dob,expected_missing",
        [
            ("", "Jane", date(1990, 1, 1), ["last_name"]),
            (None, "Jane", date(1990, 1, 1), ["last_name"]),
            ("Doe", "", date(1990, 1, 1), ["first_name"]),
            ("Doe", "Jane", None, ["date_of_birth"]),
            ("", "", None, ["last_name", "first_name", "date_of_birth"]),
        ],
    )
    def test_pre_002_rejects_missing_required_fields(self, last, first, dob, expected_missing):
        with pytest.raises(IdentityFieldsMissing) as exc:
            IdentityAnchor.mint(
                client_request_id=_crid(),
                last_name=last,
                first_name=first,
                date_of_birth=dob,
                contact_details=None,
                actor=_actor(),
            )
        assert exc.value.code == "IDENTITY_FIELDS_MISSING"
        for f in expected_missing:
            assert f in exc.value.message

    def test_two_mints_produce_different_ids(self):
        a = IdentityAnchor.mint(
            client_request_id=ClientRequestId("018f8e10-1111-7000-8000-000000000001"),
            last_name="Doe", first_name="Jane", date_of_birth=date(1990, 1, 15),
            contact_details=None, actor=_actor(),
        )
        b = IdentityAnchor.mint(
            client_request_id=ClientRequestId("018f8e10-1111-7000-8000-000000000002"),
            last_name="Doe", first_name="Jane", date_of_birth=date(1990, 1, 15),
            contact_details=None, actor=_actor(),
        )
        assert a.internal_id != b.internal_id

    def test_internal_id_validation_rejects_non_uuidv7(self):
        with pytest.raises(ValueError):
            InternalId("not-a-uuid")
        with pytest.raises(ValueError):
            # Wrong version nibble (4 instead of 7).
            InternalId("018f8e10-0000-4000-8000-000000000001")
