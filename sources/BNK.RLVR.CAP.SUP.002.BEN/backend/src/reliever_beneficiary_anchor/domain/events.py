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
    AnchorStatus,
    ContactDetails,
    InternalId,
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
class AnchorArchivedEvent:
    """Emitted by AGG.IDENTITY_ANCHOR when ARCHIVE_ANCHOR is accepted.

    Carries the full POST-transition snapshot (INV.BEN.007). The PII fields
    are unchanged across the ARCHIVE transition (INV.BEN.002 — only
    anchor_status and revision move); the snapshot therefore still carries
    the live PII, but ``anchor_status`` is now ``ARCHIVED``. Maps 1:1 to the
    wire RVT with ``transition_kind = "ARCHIVED"``.
    """

    internal_id: InternalId
    last_name: str
    first_name: str
    date_of_birth: date
    contact_details: ContactDetails | None
    creation_date: date
    revision: int
    transition_kind: TransitionKind  # always "ARCHIVED" for this event
    anchor_status: AnchorStatus  # always "ARCHIVED" for this event
    command_id: str  # caller-supplied command_id of CMD.ARCHIVE_ANCHOR
    occurred_at: datetime
    actor: Actor
    reason: str  # archival reason enum — audit only, not on the RVT wire shape


@dataclass(frozen=True, slots=True)
class AnchorRestoredEvent:
    """Emitted by AGG.IDENTITY_ANCHOR when RESTORE_ANCHOR is accepted.

    Carries the full POST-transition snapshot (INV.BEN.007). PII is
    unchanged (INV.BEN.002); ``anchor_status`` flips back to ``ACTIVE``.
    Maps 1:1 to the wire RVT with ``transition_kind = "RESTORED"``.
    """

    internal_id: InternalId
    last_name: str
    first_name: str
    date_of_birth: date
    contact_details: ContactDetails | None
    creation_date: date
    revision: int
    transition_kind: TransitionKind  # always "RESTORED" for this event
    anchor_status: AnchorStatus  # always "ACTIVE" for this event
    command_id: str  # caller-supplied command_id of CMD.RESTORE_ANCHOR
    occurred_at: datetime
    actor: Actor
    reason: str  # restore reason enum — audit only


# Union of all transition events the aggregate can emit.
# TASK-003 covers MINTED + UPDATED; TASK-004 adds ARCHIVED + RESTORED;
# PSEUDONYMISED lands at TASK-005.
TransitionEvent = Union[
    AnchorMinted, AnchorUpdated, AnchorArchivedEvent, AnchorRestoredEvent
]


__all__ = [
    "AnchorMinted",
    "AnchorUpdated",
    "AnchorArchivedEvent",
    "AnchorRestoredEvent",
    "TransitionEvent",
]
