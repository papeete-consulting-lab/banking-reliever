"""Domain events emitted by the aggregate (in-process; not the wire RVT yet).

The application layer translates these into wire-format
``BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED`` payloads via the schema mapper
in ``infrastructure.messaging``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Union

from .value_objects import (
    Actor,
    ContactDetails,
    InternalId,
    PseudonymiseReason,
    TransitionKind,
)


@dataclass(frozen=True, slots=True)
class AnchorMinted:
    """Emitted by AGG.IDENTITY_ANCHOR when MINT_ANCHOR is accepted.

    Carries the full post-transition snapshot — matches RVT semantics
    (INV.BEN.007: every accepted transition emits the full post-state).
    """

    internal_id: InternalId
    last_name: str
    first_name: str
    date_of_birth: date
    contact_details: ContactDetails | None
    creation_date: date
    revision: int
    transition_kind: TransitionKind  # always "MINTED" for this event
    command_id: str  # carries the client_request_id (per RVT schema)
    occurred_at: datetime
    actor: Actor


@dataclass(frozen=True, slots=True)
class AnchorUpdated:
    """Emitted by AGG.IDENTITY_ANCHOR when UPDATE_ANCHOR is accepted.

    Carries the full POST-transition snapshot (INV.BEN.007 — snapshot
    semantics on every transition). Sticky-PII is *already* resolved at the
    aggregate: this event holds the merged anchor state, not the partial
    delta. The application layer maps this 1:1 to the wire RVT with
    ``transition_kind = "UPDATED"``.
    """

    internal_id: InternalId
    # Full snapshot — same nullability rules as the RVT schema's
    # MINTED / UPDATED / RESTORED branch (last_name / first_name / dob
    # required; contact_details may be null).
    last_name: str
    first_name: str
    date_of_birth: date
    contact_details: ContactDetails | None
    creation_date: date
    revision: int
    transition_kind: TransitionKind  # always "UPDATED" for this event
    command_id: str  # caller-supplied command_id of CMD.UPDATE_ANCHOR
    occurred_at: datetime
    actor: Actor


@dataclass(frozen=True, slots=True)
class AnchorPseudonymised:
    """Emitted by AGG.IDENTITY_ANCHOR when PSEUDONYMISE_ANCHOR is accepted.

    The PSEUDONYMISED branch of the RVT schema requires:
      * the four PII fields (last_name, first_name, date_of_birth,
        contact_details) to be ``null`` — crypto-shredded at the aggregate;
      * ``anchor_status = PSEUDONYMISED``;
      * ``pseudonymized_at`` set to the transition wall-clock;
      * ``right_exercise_id`` set to the upstream request UUIDv7.

    Snapshot semantics (INV.BEN.007) — the event carries the FULL post-
    transition state. The ``transition_kind`` is always ``PSEUDONYMISED``;
    ``reason`` and ``previous_status`` are domain-only (NOT carried on the
    wire — they live in PRJ.ANCHOR_HISTORY only) and are kept here for the
    audit log.
    """

    internal_id: InternalId
    # Crypto-shredded snapshot — PII fields are null by construction.
    last_name: None
    first_name: None
    date_of_birth: None
    contact_details: None
    anchor_status: TransitionKind  # always "PSEUDONYMISED" on the row
    creation_date: date
    pseudonymized_at: datetime
    revision: int
    transition_kind: TransitionKind  # always "PSEUDONYMISED"
    command_id: str
    right_exercise_id: str
    reason: PseudonymiseReason
    previous_status: TransitionKind  # ACTIVE | ARCHIVED — observability only
    occurred_at: datetime
    actor: Actor


# Union of all transition events the aggregate can emit.
# TASK-003 added UPDATED; TASK-005 adds PSEUDONYMISED.
# ARCHIVED / RESTORED land at TASK-004 (not in main yet).
TransitionEvent = Union[AnchorMinted, AnchorUpdated, AnchorPseudonymised]


__all__ = [
    "AnchorMinted",
    "AnchorUpdated",
    "AnchorPseudonymised",
    "TransitionEvent",
]
