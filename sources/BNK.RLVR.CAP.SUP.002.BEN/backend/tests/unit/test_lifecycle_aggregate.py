"""Domain-layer tests for the ARCHIVE / RESTORE paths on AGG.IDENTITY_ANCHOR
(TASK-004).

Covers INV.BEN.004 (ACTIVE→ARCHIVED), INV.BEN.005 (ARCHIVED→ACTIVE),
INV.BEN.002 (PII unchanged across the lifecycle), INV.BEN.007 (one
full-state event per transition) and the state-machine guards.
"""

from __future__ import annotations

from datetime import date

import pytest

from reliever_beneficiary_anchor.domain.aggregate import IdentityAnchor
from reliever_beneficiary_anchor.domain.errors import (
    AnchorAlreadyArchived,
    AnchorNotArchived,
    AnchorPseudonymised,
)
from reliever_beneficiary_anchor.domain.events import (
    AnchorArchivedEvent,
    AnchorRestoredEvent,
)
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
    contact: ContactDetails | None = None,
    anchor_status: str = "ACTIVE",
    revision: int = 1,
) -> IdentityAnchor:
    return IdentityAnchor.hydrate(
        internal_id=_INTERNAL_ID,
        last_name="Dupont",
        first_name="Marie",
        date_of_birth=date(1985, 6, 21),
        contact_details=contact,
        anchor_status=anchor_status,  # type: ignore[arg-type]
        creation_date=date(2024, 1, 15),
        revision=revision,
    )


class TestArchive:
    def test_active_anchor_flips_to_archived(self):
        anchor = _existing(revision=3)
        anchor.archive(
            command_id="018f8e10-aaaa-7000-8000-000000000001",
            reason="PROGRAMME_EXIT_SUCCESS",
            actor=_actor(),
        )
        assert anchor.anchor_status == "ARCHIVED"
        assert anchor.revision == 4

    def test_pii_unchanged_across_archive(self):
        contact = ContactDetails(email="marie@example.org", phone="+33 1")
        anchor = _existing(contact=contact)
        anchor.archive(
            command_id="018f8e10-aaaa-7000-8000-000000000002",
            reason="ADMINISTRATIVE_ARCHIVAL",
            actor=_actor(),
        )
        assert anchor.pii.last_name == "Dupont"
        assert anchor.pii.first_name == "Marie"
        assert anchor.pii.date_of_birth == date(1985, 6, 21)
        assert anchor.pii.contact_details == contact

    def test_emits_one_archived_event_with_full_snapshot(self):
        anchor = _existing()
        cid = "018f8e10-aaaa-7000-8000-000000000003"
        anchor.archive(command_id=cid, reason="PROGRAMME_EXIT_DROPOUT", actor=_actor())
        events = anchor.pull_pending_events()
        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, AnchorArchivedEvent)
        assert evt.transition_kind == "ARCHIVED"
        assert evt.anchor_status == "ARCHIVED"
        assert evt.revision == 2
        assert evt.command_id == cid
        assert evt.last_name == "Dupont"
        assert evt.reason == "PROGRAMME_EXIT_DROPOUT"

    def test_records_last_processed_command_id(self):
        anchor = _existing()
        cid = "018f8e10-aaaa-7000-8000-000000000004"
        anchor.archive(command_id=cid, reason="PROGRAMME_EXIT_TRANSFER", actor=_actor())
        assert anchor.last_processed_command_id == cid

    def test_already_archived_rejects(self):
        anchor = _existing(anchor_status="ARCHIVED")
        with pytest.raises(AnchorAlreadyArchived) as exc:
            anchor.archive(
                command_id="018f8e10-aaaa-7000-8000-000000000005",
                reason="PROGRAMME_EXIT_SUCCESS",
                actor=_actor(),
            )
        assert exc.value.code == "ANCHOR_ALREADY_ARCHIVED"

    def test_pseudonymised_rejects(self):
        anchor = _existing(anchor_status="PSEUDONYMISED")
        with pytest.raises(AnchorPseudonymised) as exc:
            anchor.archive(
                command_id="018f8e10-aaaa-7000-8000-000000000006",
                reason="PROGRAMME_EXIT_SUCCESS",
                actor=_actor(),
            )
        assert exc.value.code == "ANCHOR_PSEUDONYMISED"


class TestRestore:
    def test_archived_anchor_flips_to_active(self):
        anchor = _existing(anchor_status="ARCHIVED", revision=5)
        anchor.restore(
            command_id="018f8e10-aaaa-7000-8000-000000000010",
            reason="ARCHIVED_IN_ERROR",
            actor=_actor(),
        )
        assert anchor.anchor_status == "ACTIVE"
        assert anchor.revision == 6

    def test_pii_unchanged_across_restore(self):
        contact = ContactDetails(
            email="marie@example.org",
            postal_address=PostalAddress(line1="1 rue X", city="Paris", country="FR"),
        )
        anchor = _existing(anchor_status="ARCHIVED", contact=contact)
        anchor.restore(
            command_id="018f8e10-aaaa-7000-8000-000000000011",
            reason="REINSTATED_AFTER_REVIEW",
            actor=_actor(),
        )
        assert anchor.pii.last_name == "Dupont"
        assert anchor.pii.contact_details == contact

    def test_emits_one_restored_event(self):
        anchor = _existing(anchor_status="ARCHIVED")
        cid = "018f8e10-aaaa-7000-8000-000000000012"
        anchor.restore(command_id=cid, reason="ARCHIVED_IN_ERROR", actor=_actor())
        events = anchor.pull_pending_events()
        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, AnchorRestoredEvent)
        assert evt.transition_kind == "RESTORED"
        assert evt.anchor_status == "ACTIVE"
        assert evt.revision == 2

    def test_active_anchor_rejects(self):
        anchor = _existing(anchor_status="ACTIVE")
        with pytest.raises(AnchorNotArchived) as exc:
            anchor.restore(
                command_id="018f8e10-aaaa-7000-8000-000000000013",
                reason="ARCHIVED_IN_ERROR",
                actor=_actor(),
            )
        assert exc.value.code == "ANCHOR_NOT_ARCHIVED"

    def test_pseudonymised_rejects(self):
        anchor = _existing(anchor_status="PSEUDONYMISED")
        with pytest.raises(AnchorPseudonymised) as exc:
            anchor.restore(
                command_id="018f8e10-aaaa-7000-8000-000000000014",
                reason="ARCHIVED_IN_ERROR",
                actor=_actor(),
            )
        assert exc.value.code == "ANCHOR_PSEUDONYMISED"


class TestRoundTrip:
    def test_active_archive_restore_round_trip(self):
        anchor = _existing(revision=1)
        anchor.archive(
            command_id="018f8e10-aaaa-7000-8000-000000000020",
            reason="PROGRAMME_EXIT_SUCCESS",
            actor=_actor(),
        )
        anchor.pull_pending_events()
        assert anchor.anchor_status == "ARCHIVED"
        assert anchor.revision == 2

        anchor.restore(
            command_id="018f8e10-aaaa-7000-8000-000000000021",
            reason="REINSTATED_AFTER_REVIEW",
            actor=_actor(),
        )
        assert anchor.anchor_status == "ACTIVE"
        assert anchor.revision == 3
        # PII identical to the seed throughout.
        assert anchor.pii.last_name == "Dupont"
        assert anchor.pii.first_name == "Marie"
        assert anchor.pii.date_of_birth == date(1985, 6, 21)
