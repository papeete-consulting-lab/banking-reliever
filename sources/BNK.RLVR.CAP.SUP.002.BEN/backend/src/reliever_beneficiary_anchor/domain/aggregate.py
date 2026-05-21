"""AGG.SUP.002.BEN.IDENTITY_ANCHOR — the consistency boundary for one anchor.

This module is the canonical place where the invariants of the aggregate
are enforced. The application layer orchestrates persistence and outbox
writes around the aggregate, but it cannot reach inside the aggregate to
mutate state directly — every transition goes through a method here.

TASK-002 implemented MINT. TASK-003 adds UPDATE. ARCHIVE / RESTORE /
PSEUDONYMISE land at TASK-004 / TASK-005.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from uuid_extensions import uuid7

from .errors import (
    AnchorArchived,
    AnchorPseudonymised,
    IdentityFieldsMissing,
    InternalIdImmutable,
    NoFieldsToUpdate,
)
from .events import AnchorMinted, AnchorUpdated, TransitionEvent
from .value_objects import (
    Actor,
    AnchorStatus,
    ClientRequestId,
    ContactDetails,
    InternalId,
    Pii,
    PostalAddress,
)

if TYPE_CHECKING:  # pragma: no cover — only for typing
    from ..application.dto import UpdateFields


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _mint_uuidv7() -> str:
    """RFC-9562 §5.7 UUIDv7. Wall-clock prefixed, k-sortable, version=7."""
    return str(uuid7())


@dataclass(slots=True)
class IdentityAnchor:
    """The aggregate root. Holds state + enforces invariants."""

    internal_id: InternalId
    pii: Pii
    anchor_status: AnchorStatus
    creation_date: date
    revision: int
    pseudonymized_at: datetime | None = None
    last_processed_command_id: str | None = None
    last_processed_client_request_id: str | None = None
    # Pending domain events buffered for the application layer to translate
    # into outbox rows. Cleared once persisted.
    _pending_events: list[TransitionEvent] = field(default_factory=list)

    # ─── Factory — MINT_ANCHOR ─────────────────────────────────────────

    @classmethod
    def mint(
        cls,
        *,
        client_request_id: ClientRequestId,
        last_name: str | None,
        first_name: str | None,
        date_of_birth: date | None,
        contact_details: ContactDetails | None,
        actor: Actor,
    ) -> "IdentityAnchor":
        """Mint a new anchor and buffer the MINTED domain event.

        Enforces:
          - INV.BEN.001 — server mints UUIDv7 (no caller-supplied id reaches here)
          - INV.BEN.007 — emits exactly one event carrying the full post-state
          - INV.BEN.008 — caller-side; idempotency is enforced at the application
            boundary against the idempotency_keys table.

        Raises ``IdentityFieldsMissing`` (PRE.002) if any required field is
        missing or empty.
        """
        # PRE.002 — required identity fields.
        missing: list[str] = []
        if not last_name:
            missing.append("last_name")
        if not first_name:
            missing.append("first_name")
        if date_of_birth is None:
            missing.append("date_of_birth")
        if missing:
            raise IdentityFieldsMissing(missing)

        # INV.BEN.001 — server mints. The aggregate is the only legitimate
        # source of internal_id. No caller-supplied id flows into this method.
        internal_id = InternalId(_mint_uuidv7())
        now = _now_utc()

        anchor = cls(
            internal_id=internal_id,
            pii=Pii(
                last_name=last_name,
                first_name=first_name,
                date_of_birth=date_of_birth,
                contact_details=contact_details,
            ),
            anchor_status="ACTIVE",
            creation_date=now.date(),
            revision=1,
            pseudonymized_at=None,
            last_processed_command_id=None,
            last_processed_client_request_id=str(client_request_id),
        )

        # INV.BEN.007 — emit ONE event per transition with the full snapshot.
        anchor._pending_events.append(
            AnchorMinted(
                internal_id=internal_id,
                last_name=last_name,  # type: ignore[arg-type] — guarded above
                first_name=first_name,  # type: ignore[arg-type]
                date_of_birth=date_of_birth,  # type: ignore[arg-type]
                contact_details=contact_details,
                creation_date=anchor.creation_date,
                revision=anchor.revision,
                transition_kind="MINTED",
                command_id=str(client_request_id),
                occurred_at=now,
                actor=actor,
            )
        )
        return anchor

    # ─── Factory — hydrate from a persisted row ────────────────────────

    @classmethod
    def hydrate(
        cls,
        *,
        internal_id: str,
        last_name: str | None,
        first_name: str | None,
        date_of_birth: date | None,
        contact_details: ContactDetails | None,
        anchor_status: AnchorStatus,
        creation_date: date,
        revision: int,
        pseudonymized_at: datetime | None = None,
        last_processed_command_id: str | None = None,
        last_processed_client_request_id: str | None = None,
    ) -> "IdentityAnchor":
        """Rebuild an aggregate from a persisted row.

        This is the load-path used by every lifecycle handler — it does
        NOT emit any event and does NOT increment revision. The aggregate
        is reconstituted in the exact state observed on disk.
        """
        return cls(
            internal_id=InternalId(internal_id),
            pii=Pii(
                last_name=last_name,
                first_name=first_name,
                date_of_birth=date_of_birth,
                contact_details=contact_details,
            ),
            anchor_status=anchor_status,
            creation_date=creation_date,
            revision=revision,
            pseudonymized_at=pseudonymized_at,
            last_processed_command_id=last_processed_command_id,
            last_processed_client_request_id=last_processed_client_request_id,
        )

    # ─── Command — UPDATE_ANCHOR ───────────────────────────────────────

    def update(
        self,
        *,
        command_id: str,
        fields: "UpdateFields",
        actor: Actor,
    ) -> None:
        """Apply a partial PII update under the sticky-PII rule (INV.BEN.003).

        ``fields`` is an ``UpdateFields`` value object that distinguishes
        three states per field:

          * UNSET    — field absent from the payload (no-op, sticky)
          * CLEAR    — explicit ``null`` on a contact channel (clears it)
          * <value>  — explicit value (replaces)

        Enforces:
          - INV.BEN.002 — internal_id immutable (the path parameter is
            verified at the application boundary; the aggregate has no
            method to change it and ignores any ``internal_id`` carried in
            ``fields`` by raising InternalIdImmutable).
          - INV.BEN.003 — sticky-PII: only present fields are touched.
          - INV.BEN.007 — emits exactly one AnchorUpdated event with the
            full post-state snapshot.
          - Lifecycle guards:
              * ARCHIVED      → AnchorArchived (409)
              * PSEUDONYMISED → AnchorPseudonymised (409)

        Raises ``NoFieldsToUpdate`` if ``fields`` carries no mutable
        field after applying sticky-PII semantics (empty payload).
        """
        # Lifecycle guards — drive the 409 responses.
        if self.anchor_status == "ARCHIVED":
            raise AnchorArchived(str(self.internal_id))
        if self.anchor_status == "PSEUDONYMISED":
            raise AnchorPseudonymised(str(self.internal_id))
        # By construction the only remaining state is ACTIVE — the literal
        # union forbids anything else, but assert to make the invariant
        # explicit for readers.
        assert self.anchor_status == "ACTIVE"

        # INV.BEN.002 — internal_id is never carried in the body; this is
        # a defence-in-depth check the presentation layer also enforces.
        if fields.attempts_internal_id_mutation:
            raise InternalIdImmutable()

        # INV.BEN.003 — sticky-PII merge.
        if not fields.has_any_mutation:
            raise NoFieldsToUpdate()

        new_last_name = fields.merge_last_name(self.pii.last_name)
        new_first_name = fields.merge_first_name(self.pii.first_name)
        new_dob = fields.merge_date_of_birth(self.pii.date_of_birth)
        new_contact = fields.merge_contact_details(self.pii.contact_details)

        # The MINTED/UPDATED/RESTORED branch of the RVT schema requires
        # last_name + first_name + date_of_birth to be non-null. The
        # sticky-PII merge preserves them when the caller doesn't touch
        # them, and only an explicit empty string / null could violate
        # them — but the UPDATE schema rejects empty strings (minLength=1)
        # and rejects nulls on these required PII fields. The path here is
        # therefore unreachable under a valid wire payload, but we assert
        # to fail loudly if the schema ever drifts.
        assert new_last_name is not None, "last_name must remain set (INV.BEN.007)"
        assert new_first_name is not None, "first_name must remain set (INV.BEN.007)"
        assert new_dob is not None, "date_of_birth must remain set (INV.BEN.007)"

        now = _now_utc()
        self.pii = Pii(
            last_name=new_last_name,
            first_name=new_first_name,
            date_of_birth=new_dob,
            contact_details=new_contact,
        )
        self.revision += 1
        self.last_processed_command_id = command_id

        self._pending_events.append(
            AnchorUpdated(
                internal_id=self.internal_id,
                last_name=new_last_name,
                first_name=new_first_name,
                date_of_birth=new_dob,
                contact_details=new_contact,
                creation_date=self.creation_date,
                revision=self.revision,
                transition_kind="UPDATED",
                command_id=command_id,
                occurred_at=now,
                actor=actor,
            )
        )

    # ─── Pending events ────────────────────────────────────────────────

    def pull_pending_events(self) -> list[TransitionEvent]:
        events = list(self._pending_events)
        self._pending_events.clear()
        return events


__all__ = ["IdentityAnchor"]
