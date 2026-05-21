"""Domain-layer tests for the UPDATE path on AGG.IDENTITY_ANCHOR.

Covers INV.BEN.002 (immutability of internal_id), INV.BEN.003 (sticky-PII),
INV.BEN.007 (full-state event), and the lifecycle guards (ARCHIVED /
PSEUDONYMISED).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from reliever_beneficiary_anchor.application.dto import (
    UNSET,
    ContactDetailsUpdate,
    UpdateFields,
)
from reliever_beneficiary_anchor.domain.aggregate import IdentityAnchor
from reliever_beneficiary_anchor.domain.errors import (
    AnchorArchived,
    AnchorPseudonymised,
    InternalIdImmutable,
    NoFieldsToUpdate,
)
from reliever_beneficiary_anchor.domain.events import AnchorUpdated
from reliever_beneficiary_anchor.domain.value_objects import (
    Actor,
    ContactDetails,
    PostalAddress,
)


_INTERNAL_ID = "018f8e10-9999-7000-8000-000000000001"


def _actor() -> Actor:
    return Actor(kind="human", subject="018f8e10-2222-7000-8000-0000000000aa")


def _existing(
    *,
    last_name: str = "Dupont",
    first_name: str = "Marie",
    date_of_birth: date = date(1985, 6, 21),
    contact: ContactDetails | None = None,
    anchor_status: str = "ACTIVE",
    revision: int = 1,
) -> IdentityAnchor:
    return IdentityAnchor.hydrate(
        internal_id=_INTERNAL_ID,
        last_name=last_name,
        first_name=first_name,
        date_of_birth=date_of_birth,
        contact_details=contact,
        anchor_status=anchor_status,  # type: ignore[arg-type]
        creation_date=date(2024, 1, 15),
        revision=revision,
    )


class TestStickyPiiSemantics:
    """INV.BEN.003 — sticky-PII rule."""

    def test_absent_field_is_no_op(self):
        anchor = _existing(contact=ContactDetails(email="marie@example.org"))
        # Only first_name carried; last_name + dob + contact must be untouched.
        anchor.update(
            command_id="018f8e10-bbbb-7000-8000-000000000001",
            fields=UpdateFields(first_name="Maryam"),
            actor=_actor(),
        )
        assert anchor.pii.last_name == "Dupont"  # unchanged
        assert anchor.pii.first_name == "Maryam"  # replaced
        assert anchor.pii.date_of_birth == date(1985, 6, 21)  # unchanged
        # contact_details must be EXACTLY preserved (sticky).
        assert anchor.pii.contact_details is not None
        assert anchor.pii.contact_details.email == "marie@example.org"

    def test_explicit_value_replaces(self):
        anchor = _existing()
        anchor.update(
            command_id="018f8e10-bbbb-7000-8000-000000000002",
            fields=UpdateFields(
                last_name="Martin",
                first_name="Marianne",
                date_of_birth=date(1986, 1, 1),
            ),
            actor=_actor(),
        )
        assert anchor.pii.last_name == "Martin"
        assert anchor.pii.first_name == "Marianne"
        assert anchor.pii.date_of_birth == date(1986, 1, 1)

    def test_explicit_null_on_email_clears_that_channel(self):
        existing_contact = ContactDetails(
            email="marie@example.org",
            phone="+33 1 23 45 67 89",
            postal_address=PostalAddress(line1="1 rue X", city="Paris", country="FR"),
        )
        anchor = _existing(contact=existing_contact)
        anchor.update(
            command_id="018f8e10-bbbb-7000-8000-000000000003",
            fields=UpdateFields(
                contact_details=ContactDetailsUpdate(email=None),  # ← clear email
            ),
            actor=_actor(),
        )
        assert anchor.pii.contact_details is not None
        assert anchor.pii.contact_details.email is None
        # Other channels untouched (sticky within contact_details too).
        assert anchor.pii.contact_details.phone == "+33 1 23 45 67 89"
        assert anchor.pii.contact_details.postal_address is not None
        assert anchor.pii.contact_details.postal_address.city == "Paris"

    def test_explicit_null_on_phone_clears_only_phone(self):
        existing_contact = ContactDetails(
            email="marie@example.org",
            phone="+33 1 23 45 67 89",
        )
        anchor = _existing(contact=existing_contact)
        anchor.update(
            command_id="018f8e10-bbbb-7000-8000-000000000004",
            fields=UpdateFields(
                contact_details=ContactDetailsUpdate(phone=None),
            ),
            actor=_actor(),
        )
        assert anchor.pii.contact_details is not None
        assert anchor.pii.contact_details.email == "marie@example.org"  # sticky
        assert anchor.pii.contact_details.phone is None  # cleared

    def test_explicit_null_on_postal_address_clears_only_postal(self):
        existing_contact = ContactDetails(
            email="marie@example.org",
            postal_address=PostalAddress(line1="1 rue X", city="Paris", country="FR"),
        )
        anchor = _existing(contact=existing_contact)
        anchor.update(
            command_id="018f8e10-bbbb-7000-8000-000000000005",
            fields=UpdateFields(
                contact_details=ContactDetailsUpdate(postal_address=None),
            ),
            actor=_actor(),
        )
        assert anchor.pii.contact_details is not None
        assert anchor.pii.contact_details.email == "marie@example.org"  # sticky
        assert anchor.pii.contact_details.postal_address is None

    def test_clearing_all_three_channels_yields_none_contact(self):
        existing_contact = ContactDetails(
            email="marie@example.org",
            phone="+33 1 23 45 67 89",
            postal_address=PostalAddress(line1="x"),
        )
        anchor = _existing(contact=existing_contact)
        anchor.update(
            command_id="018f8e10-bbbb-7000-8000-000000000006",
            fields=UpdateFields(
                contact_details=ContactDetailsUpdate(
                    email=None, phone=None, postal_address=None,
                ),
            ),
            actor=_actor(),
        )
        assert anchor.pii.contact_details is None  # collapsed to null


class TestLifecycleGuards:
    def test_archived_anchor_refuses_update(self):
        anchor = _existing(anchor_status="ARCHIVED")
        with pytest.raises(AnchorArchived) as exc:
            anchor.update(
                command_id="018f8e10-bbbb-7000-8000-000000000020",
                fields=UpdateFields(first_name="Maryam"),
                actor=_actor(),
            )
        assert exc.value.code == "ANCHOR_ARCHIVED"

    def test_pseudonymised_anchor_refuses_update(self):
        anchor = _existing(
            anchor_status="PSEUDONYMISED",
            last_name="****",  # placeholder — TASK-005 supplies the wipe markers
        )
        with pytest.raises(AnchorPseudonymised) as exc:
            anchor.update(
                command_id="018f8e10-bbbb-7000-8000-000000000021",
                fields=UpdateFields(first_name="Maryam"),
                actor=_actor(),
            )
        assert exc.value.code == "ANCHOR_PSEUDONYMISED"


class TestEmptyPayload:
    def test_empty_fields_raises_no_fields_to_update(self):
        anchor = _existing()
        with pytest.raises(NoFieldsToUpdate) as exc:
            anchor.update(
                command_id="018f8e10-bbbb-7000-8000-000000000030",
                fields=UpdateFields(),  # everything UNSET
                actor=_actor(),
            )
        assert exc.value.code == "NO_FIELDS_TO_UPDATE"

    def test_contact_details_with_only_unset_channels_is_no_op(self):
        anchor = _existing()
        # An UpdateFields with contact_details=ContactDetailsUpdate(...) where
        # all three channels are UNSET — counts as no mutation.
        empty_contact = ContactDetailsUpdate()
        with pytest.raises(NoFieldsToUpdate):
            anchor.update(
                command_id="018f8e10-bbbb-7000-8000-000000000031",
                fields=UpdateFields(contact_details=empty_contact),
                actor=_actor(),
            )


class TestInternalIdImmutability:
    def test_attempts_internal_id_mutation_is_rejected(self):
        anchor = _existing()
        with pytest.raises(InternalIdImmutable) as exc:
            anchor.update(
                command_id="018f8e10-bbbb-7000-8000-000000000040",
                fields=UpdateFields(
                    first_name="X", attempts_internal_id_mutation=True,
                ),
                actor=_actor(),
            )
        assert exc.value.code == "INTERNAL_ID_IMMUTABLE"

    def test_internal_id_is_preserved_after_update(self):
        anchor = _existing()
        original_id = str(anchor.internal_id)
        anchor.update(
            command_id="018f8e10-bbbb-7000-8000-000000000041",
            fields=UpdateFields(first_name="Maryam"),
            actor=_actor(),
        )
        assert str(anchor.internal_id) == original_id


class TestRevisionMonotonicity:
    def test_revision_bumped_by_one(self):
        anchor = _existing(revision=7)
        anchor.update(
            command_id="018f8e10-bbbb-7000-8000-000000000050",
            fields=UpdateFields(first_name="Maryam"),
            actor=_actor(),
        )
        assert anchor.revision == 8


class TestEmittedDomainEvent:
    def test_one_anchor_updated_event_with_full_post_state(self):
        anchor = _existing(contact=ContactDetails(email="marie@example.org"))
        anchor.update(
            command_id="018f8e10-bbbb-7000-8000-000000000060",
            fields=UpdateFields(
                first_name="Maryam",
                contact_details=ContactDetailsUpdate(email=None),  # clear email
            ),
            actor=_actor(),
        )
        events = anchor.pull_pending_events()
        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, AnchorUpdated)
        assert evt.transition_kind == "UPDATED"
        assert evt.revision == 2
        assert evt.last_name == "Dupont"      # sticky
        assert evt.first_name == "Maryam"     # replaced
        assert evt.date_of_birth == date(1985, 6, 21)  # sticky
        assert evt.command_id == "018f8e10-bbbb-7000-8000-000000000060"
        # contact_details: email was the only channel before; cleared → contact = None
        assert evt.contact_details is None

    def test_last_processed_command_id_recorded_on_aggregate(self):
        anchor = _existing()
        cid = "018f8e10-bbbb-7000-8000-000000000061"
        anchor.update(
            command_id=cid,
            fields=UpdateFields(first_name="Maryam"),
            actor=_actor(),
        )
        assert anchor.last_processed_command_id == cid
