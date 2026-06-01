"""Unit tests for IdentityAnchor.pseudonymise() — TASK-005.

Pure aggregate-level tests with no I/O — pins the invariants that
constrain the GDPR Art. 17 crypto-shred semantics:

  * INV.BEN.002 — internal_id is unchanged.
  * INV.BEN.006 — accepts from ACTIVE or ARCHIVED; rejects PSEUDONYMISED.
  * INV.BEN.007 — exactly one AnchorPseudonymised event with full snapshot
    (four PII fields null, transition_kind=PSEUDONYMISED, revision=N+1,
    pseudonymized_at set, right_exercise_id set).
  * Crypto-shred post-condition — the aggregate severs ``crypto_key_id``
    and exposes the prior id via ``pull_shredded_crypto_key_id()`` so the
    application layer can delete the DEK row in the same transaction.
"""

from __future__ import annotations

import uuid
from datetime import date, timezone

import pytest
from uuid_extensions import uuid7

from reliever_beneficiary_anchor.domain.aggregate import IdentityAnchor
from reliever_beneficiary_anchor.domain.errors import (
    AnchorAlreadyPseudonymised,
    RightExerciseIdInvalid,
)
from reliever_beneficiary_anchor.domain.events import (
    AnchorMinted,
    AnchorPseudonymised,
)
from reliever_beneficiary_anchor.domain.value_objects import (
    Actor,
    ClientRequestId,
    ContactDetails,
    RightExerciseId,
)


def _uuidv7() -> str:
    return str(uuid7())


def _human_actor() -> Actor:
    return Actor(kind="human", subject=_uuidv7())


def _mint_anchor(
    *,
    crypto_key_id: str | None = None,
    anchor_status: str = "ACTIVE",
) -> IdentityAnchor:
    """Helper — mint a fresh anchor in ACTIVE state, then optionally flip
    its status (e.g. to ARCHIVED) via a direct attribute write, since the
    ARCHIVE handler doesn't live in this worktree's main yet (TASK-004 is
    in a branch). We only need this for the INV.BEN.006 transitions test.
    """
    crid = ClientRequestId(_uuidv7())
    crypto_key = crypto_key_id or _uuidv7()
    anchor = IdentityAnchor.mint(
        client_request_id=crid,
        last_name="Dupont",
        first_name="Marie",
        date_of_birth=date(1985, 6, 21),
        contact_details=ContactDetails(
            email="marie.dupont@example.org",
            phone="+33 1 23 45 67 89",
        ),
        actor=_human_actor(),
        crypto_key_id=crypto_key,
    )
    # Drain MINTED event before pseudonymising.
    minted = anchor.pull_pending_events()
    assert len(minted) == 1 and isinstance(minted[0], AnchorMinted)
    if anchor_status != "ACTIVE":
        anchor.anchor_status = anchor_status  # type: ignore[assignment]
    return anchor


# ─── INV.BEN.006 — accepted source states ──────────────────────────────


def test_pseudonymise_active_anchor_succeeds():
    crypto_key_id = _uuidv7()
    anchor = _mint_anchor(crypto_key_id=crypto_key_id)
    cmd_id = _uuidv7()
    right_id = _uuidv7()

    anchor.pseudonymise(
        command_id=cmd_id,
        right_exercise_id=RightExerciseId(right_id),
        reason="GDPR_ART17_REQUEST",
        actor=_human_actor(),
    )

    assert anchor.anchor_status == "PSEUDONYMISED"
    assert anchor.pii.last_name is None
    assert anchor.pii.first_name is None
    assert anchor.pii.date_of_birth is None
    assert anchor.pii.contact_details is None
    assert anchor.crypto_key_id is None  # severed
    assert anchor.pseudonymized_at is not None
    assert anchor.pseudonymized_at.tzinfo == timezone.utc
    assert anchor.revision == 2  # N+1
    assert anchor.last_processed_command_id == cmd_id
    # The DEK to crypto-shred at the infrastructure layer.
    assert anchor.pull_shredded_crypto_key_id() == crypto_key_id


def test_pseudonymise_archived_anchor_succeeds():
    """INV.BEN.006 — PSEUDONYMISE is accepted from ARCHIVED too."""
    anchor = _mint_anchor(anchor_status="ARCHIVED")
    anchor.pseudonymise(
        command_id=_uuidv7(),
        right_exercise_id=RightExerciseId(_uuidv7()),
        reason="DPO_INITIATED",
        actor=_human_actor(),
    )

    assert anchor.anchor_status == "PSEUDONYMISED"
    assert anchor.pii.last_name is None
    assert anchor.crypto_key_id is None


def test_pseudonymise_internal_id_is_unchanged():
    """INV.BEN.002 — even after pseudonymisation the internal_id is preserved."""
    anchor = _mint_anchor()
    before = str(anchor.internal_id)
    anchor.pseudonymise(
        command_id=_uuidv7(),
        right_exercise_id=RightExerciseId(_uuidv7()),
        reason="GDPR_ART17_REQUEST",
        actor=_human_actor(),
    )
    assert str(anchor.internal_id) == before


# ─── INV.BEN.006 — terminal state guard ────────────────────────────────


def test_pseudonymise_pseudonymised_anchor_raises_already_pseudonymised():
    anchor = _mint_anchor()
    anchor.pseudonymise(
        command_id=_uuidv7(),
        right_exercise_id=RightExerciseId(_uuidv7()),
        reason="GDPR_ART17_REQUEST",
        actor=_human_actor(),
    )
    # Drain the AnchorPseudonymised event from the first call.
    anchor.pull_pending_events()
    anchor.pull_shredded_crypto_key_id()

    with pytest.raises(AnchorAlreadyPseudonymised) as exc_info:
        anchor.pseudonymise(
            command_id=_uuidv7(),
            right_exercise_id=RightExerciseId(_uuidv7()),
            reason="GDPR_ART17_REQUEST",
            actor=_human_actor(),
        )
    assert exc_info.value.code == "ANCHOR_ALREADY_PSEUDONYMISED"


# ─── INV.BEN.007 — exactly one event with full snapshot ────────────────


def test_pseudonymise_emits_exactly_one_event_with_full_snapshot():
    crypto_key_id = _uuidv7()
    anchor = _mint_anchor(crypto_key_id=crypto_key_id)
    cmd_id = _uuidv7()
    right_id = _uuidv7()
    actor = _human_actor()

    anchor.pseudonymise(
        command_id=cmd_id,
        right_exercise_id=RightExerciseId(right_id),
        reason="REGULATORY_ORDER",
        actor=actor,
    )

    events = anchor.pull_pending_events()
    assert len(events) == 1
    ev = events[0]
    assert isinstance(ev, AnchorPseudonymised)
    assert ev.transition_kind == "PSEUDONYMISED"
    assert ev.anchor_status == "PSEUDONYMISED"
    assert ev.last_name is None
    assert ev.first_name is None
    assert ev.date_of_birth is None
    assert ev.contact_details is None
    assert ev.revision == 2
    assert ev.command_id == cmd_id
    assert ev.right_exercise_id == right_id
    assert ev.reason == "REGULATORY_ORDER"
    assert ev.actor == actor
    assert ev.pseudonymized_at == anchor.pseudonymized_at
    assert ev.occurred_at == anchor.pseudonymized_at
    # previous_status is captured for audit (MINTED proxy for ACTIVE)
    assert ev.previous_status in ("MINTED", "ARCHIVED")


def test_pseudonymise_does_not_emit_for_failed_terminal_guard():
    anchor = _mint_anchor()
    anchor.pseudonymise(
        command_id=_uuidv7(),
        right_exercise_id=RightExerciseId(_uuidv7()),
        reason="GDPR_ART17_REQUEST",
        actor=_human_actor(),
    )
    anchor.pull_pending_events()

    with pytest.raises(AnchorAlreadyPseudonymised):
        anchor.pseudonymise(
            command_id=_uuidv7(),
            right_exercise_id=RightExerciseId(_uuidv7()),
            reason="GDPR_ART17_REQUEST",
            actor=_human_actor(),
        )

    # No event was buffered for the rejected attempt.
    assert anchor.pull_pending_events() == []


# ─── PRE.004 — right_exercise_id guards ────────────────────────────────


def test_right_exercise_id_vo_rejects_non_uuidv7():
    """``RightExerciseId`` constructor rejects ill-formed UUIDs."""
    with pytest.raises(ValueError):
        RightExerciseId("not-a-uuid")
    with pytest.raises(ValueError):
        # UUIDv4 — wrong version nibble.
        RightExerciseId(str(uuid.uuid4()))


def test_pseudonymise_rejects_non_vo_right_exercise_id():
    """Defence-in-depth: the aggregate refuses raw strings as right_exercise_id."""
    anchor = _mint_anchor()
    with pytest.raises(RightExerciseIdInvalid):
        anchor.pseudonymise(
            command_id=_uuidv7(),
            right_exercise_id="raw-string-not-vo",  # type: ignore[arg-type]
            reason="GDPR_ART17_REQUEST",
            actor=_human_actor(),
        )


# ─── pull_shredded_crypto_key_id semantics ─────────────────────────────


def test_pull_shredded_crypto_key_id_is_one_shot():
    anchor = _mint_anchor(crypto_key_id=_uuidv7())
    anchor.pseudonymise(
        command_id=_uuidv7(),
        right_exercise_id=RightExerciseId(_uuidv7()),
        reason="GDPR_ART17_REQUEST",
        actor=_human_actor(),
    )
    first = anchor.pull_shredded_crypto_key_id()
    assert first is not None
    # Second call yields None — drained.
    second = anchor.pull_shredded_crypto_key_id()
    assert second is None


def test_pull_shredded_crypto_key_id_is_none_on_non_pseudonymising_path():
    anchor = _mint_anchor(crypto_key_id=_uuidv7())
    # No pseudonymise call → no shred pending.
    assert anchor.pull_shredded_crypto_key_id() is None
