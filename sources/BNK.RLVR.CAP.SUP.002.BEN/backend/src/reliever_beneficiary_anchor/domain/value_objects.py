"""Value objects of the identity anchor aggregate.

All value objects are immutable (``frozen=True``) and validated at
construction time. They carry no I/O dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

# RFC-9562 §5.7 — UUIDv7: version nibble = 7, variant nibble in {8,9,a,b}.
_UUIDV7_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

ActorKind = Literal["human", "service", "system"]
AnchorStatus = Literal["ACTIVE", "ARCHIVED", "PSEUDONYMISED"]
TransitionKind = Literal["MINTED", "UPDATED", "ARCHIVED", "RESTORED", "PSEUDONYMISED"]


@dataclass(frozen=True, slots=True)
class InternalId:
    """The server-minted UUIDv7 anchor identifier (INV.BEN.001 / 002)."""

    value: str

    def __post_init__(self) -> None:
        if not _UUIDV7_RE.match(self.value):
            raise ValueError(
                f"internal_id is not a RFC-9562 UUIDv7: {self.value!r}"
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ClientRequestId:
    """Caller-supplied UUIDv7 idempotency anchor for MINT_ANCHOR (INV.BEN.008)."""

    value: str

    def __post_init__(self) -> None:
        if not _UUIDV7_RE.match(self.value):
            raise ValueError(
                f"client_request_id is not a RFC-9562 UUIDv7: {self.value!r}"
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PostalAddress:
    line1: str | None = None
    line2: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str | None = None  # ISO 3166-1 alpha-2 or alpha-3

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass(frozen=True, slots=True)
class ContactDetails:
    email: str | None = None
    phone: str | None = None
    postal_address: PostalAddress | None = None

    def to_dict(self) -> dict:
        out: dict = {}
        if self.email is not None:
            out["email"] = self.email
        if self.phone is not None:
            out["phone"] = self.phone
        if self.postal_address is not None:
            out["postal_address"] = self.postal_address.to_dict()
        return out

    @classmethod
    def from_dict(cls, data: dict | None) -> "ContactDetails | None":
        if data is None:
            return None
        postal = data.get("postal_address")
        return cls(
            email=data.get("email"),
            phone=data.get("phone"),
            postal_address=PostalAddress(**postal) if postal else None,
        )


@dataclass(frozen=True, slots=True)
class Pii:
    """The personally-identifiable bundle. Wipeable under PSEUDONYMISE.

    TASK-002 only mints anchors with non-null PII; the wipe path lands at
    TASK-005. We model the fields as ``str | None`` here so the same VO
    can carry pseudonymised state in later tasks without a refactor.
    """

    last_name: str | None
    first_name: str | None
    date_of_birth: date | None
    contact_details: ContactDetails | None

    def required_fields_present(self) -> bool:
        return bool(self.last_name) and bool(self.first_name) and self.date_of_birth is not None


@dataclass(frozen=True, slots=True)
class Actor:
    """Principal that issued the command (envelope.actor in RVT)."""

    kind: ActorKind
    subject: str
    on_behalf_of: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        out: dict[str, str | None] = {"kind": self.kind, "subject": self.subject}
        if self.on_behalf_of is not None:
            out["on_behalf_of"] = self.on_behalf_of
        return out

    @classmethod
    def system_anonymous(cls) -> "Actor":
        return cls(kind="system", subject="system:anonymous")
