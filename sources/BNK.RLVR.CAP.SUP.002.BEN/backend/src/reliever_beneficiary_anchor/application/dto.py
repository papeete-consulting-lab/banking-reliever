"""DTOs crossing the application boundary.

These are *internal* — the presentation layer maps them to JSON; the schema
validator works on dicts. The wire-format BeneficiaryAnchor is what the
HTTP responses serialise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, ClassVar, Final

from ..domain.value_objects import Actor, ContactDetails, PostalAddress


# ─── Sentinels for sticky-PII (INV.BEN.003) ────────────────────────────


class _Unset:
    """Singleton sentinel marking a field as absent from an UPDATE payload.

    Used to distinguish "no key in JSON" (sticky — leave value alone) from
    "key present with explicit ``null``" (clear — only valid on contact
    channels). This is the cleanest Python encoding of the JSON
    distinction we need for sticky-PII semantics, and lives at the
    application boundary so the wire body is parsed only once.
    """

    _instance: ClassVar["_Unset | None"] = None

    def __new__(cls) -> "_Unset":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover — debug aid
        return "<UNSET>"

    def __bool__(self) -> bool:  # pragma: no cover
        return False


UNSET: Final[_Unset] = _Unset()


@dataclass(frozen=True, slots=True)
class ContactDetailsUpdate:
    """Sticky-PII contact-channels update.

    Each channel is encoded as one of:
      - ``UNSET``    (key absent in JSON — channel unchanged)
      - ``None``     (explicit ``null`` in JSON — channel cleared)
      - ``str`` / ``PostalAddress`` (explicit value — channel replaced)

    The ``presence`` semantics are driven by which key was in the request
    JSON, not by the value of the field (which can legitimately be
    ``None`` to mean "clear").
    """

    email: str | None | _Unset = UNSET
    phone: str | None | _Unset = UNSET
    postal_address: PostalAddress | None | _Unset = UNSET

    @property
    def has_any_mutation(self) -> bool:
        return not (
            self.email is UNSET
            and self.phone is UNSET
            and self.postal_address is UNSET
        )

    def merge(self, current: ContactDetails | None) -> ContactDetails | None:
        """Apply sticky-PII merge against ``current`` and return the new
        contact_details. Returns ``None`` only if the resulting state has
        all three channels unset / cleared (so the wire RVT carries
        ``contact_details: null`` per the canonical schema).
        """
        base = current or ContactDetails(email=None, phone=None, postal_address=None)

        new_email = base.email if self.email is UNSET else self.email  # type: ignore[assignment]
        new_phone = base.phone if self.phone is UNSET else self.phone  # type: ignore[assignment]
        new_postal = (
            base.postal_address
            if self.postal_address is UNSET
            else self.postal_address  # type: ignore[assignment]
        )

        if new_email is None and new_phone is None and new_postal is None:
            return None
        return ContactDetails(
            email=new_email,  # type: ignore[arg-type]
            phone=new_phone,  # type: ignore[arg-type]
            postal_address=new_postal,  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class UpdateFields:
    """Sticky-PII delta carried by CMD.UPDATE_ANCHOR.

    Encodes per-field presence using the ``UNSET`` sentinel so the
    aggregate can apply the merge of INV.BEN.003 without re-reading the
    wire body. The presentation layer is responsible for constructing
    this from the raw request dict (where ``key in body`` is the
    authoritative presence signal).

    ``attempts_internal_id_mutation`` is True if the wire payload tried to
    carry an ``internal_id`` field — defence-in-depth for INV.BEN.002
    (the canonical UPDATE schema sets ``additionalProperties: false`` so
    this should never reach us, but the assertion still costs nothing).
    """

    last_name: str | _Unset = UNSET
    first_name: str | _Unset = UNSET
    date_of_birth: date | _Unset = UNSET
    contact_details: ContactDetailsUpdate | _Unset = UNSET
    attempts_internal_id_mutation: bool = False

    @property
    def has_any_mutation(self) -> bool:
        """True if the payload carries at least one mutable field
        (post-stripping of ``command_id``). Drives the
        NO_FIELDS_TO_UPDATE branch.
        """
        if not (
            self.last_name is UNSET
            and self.first_name is UNSET
            and self.date_of_birth is UNSET
        ):
            return True
        if isinstance(self.contact_details, ContactDetailsUpdate):
            return self.contact_details.has_any_mutation
        return False

    # ─── Sticky-PII merge primitives ───────────────────────────────────

    def merge_last_name(self, current: str | None) -> str | None:
        return current if self.last_name is UNSET else self.last_name  # type: ignore[return-value]

    def merge_first_name(self, current: str | None) -> str | None:
        return current if self.first_name is UNSET else self.first_name  # type: ignore[return-value]

    def merge_date_of_birth(self, current: date | None) -> date | None:
        return current if self.date_of_birth is UNSET else self.date_of_birth  # type: ignore[return-value]

    def merge_contact_details(
        self, current: ContactDetails | None
    ) -> ContactDetails | None:
        if self.contact_details is UNSET:
            return current
        assert isinstance(self.contact_details, ContactDetailsUpdate)
        return self.contact_details.merge(current)


@dataclass(frozen=True, slots=True)
class MintAnchorCommandDto:
    """Input payload of CMD.MINT_ANCHOR — already passed through JSON Schema
    validation at the presentation boundary.

    Note: ``internal_id`` is intentionally absent from the command DTO —
    the server mints it (INV.BEN.001). The presentation layer rejects any
    request body that carries one.
    """

    client_request_id: str
    last_name: str
    first_name: str
    date_of_birth: date
    contact_details: ContactDetails | None
    actor: Actor


@dataclass(frozen=True, slots=True)
class UpdateAnchorCommandDto:
    """Input payload of CMD.UPDATE_ANCHOR — already passed through JSON
    Schema validation at the presentation boundary.

    Sticky-PII semantics (INV.BEN.003) are encoded in ``fields``; the
    handler hands those off to ``IdentityAnchor.update(...)``.

    ``internal_id`` is the PATH parameter — it is NOT a body field.
    """

    internal_id: str
    command_id: str
    fields: UpdateFields
    actor: Actor


@dataclass(frozen=True, slots=True)
class BeneficiaryAnchorDto:
    """Canonical wire-format BeneficiaryAnchor — matches the QRY.GET_ANCHOR
    response and the 201 response of POST /anchors.

    The pseudonymised branch returns the four PII fields as None.
    """

    internal_id: str
    last_name: str | None
    first_name: str | None
    date_of_birth: date | None
    contact_details: dict[str, Any] | None
    anchor_status: str
    creation_date: date
    pseudonymized_at: datetime | None
    revision: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "internal_id": self.internal_id,
            "last_name": self.last_name,
            "first_name": self.first_name,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "contact_details": self.contact_details,
            "anchor_status": self.anchor_status,
            "creation_date": self.creation_date.isoformat(),
            "pseudonymized_at": self.pseudonymized_at.isoformat() if self.pseudonymized_at else None,
            "revision": self.revision,
        }


__all__ = [
    "BeneficiaryAnchorDto",
    "ContactDetailsUpdate",
    "MintAnchorCommandDto",
    "UNSET",
    "UpdateAnchorCommandDto",
    "UpdateFields",
    "_Unset",
]
