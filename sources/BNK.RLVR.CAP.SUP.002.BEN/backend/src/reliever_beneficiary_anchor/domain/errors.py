"""Domain-layer error codes — mirror commands.yaml.errors and the schema enums.

Each ``DomainError`` carries the canonical ``code`` declared in
``process/BNK.RLVR.CAP.SUP.002.BEN/commands.yaml`` so the presentation layer can map
directly to the HTTP response without re-stringifying.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DomainError(Exception):
    """Base class for domain-layer errors.

    The ``code`` is the canonical error code from ``commands.yaml`` (e.g.
    ``IDENTITY_FIELDS_MISSING``). The ``message`` is a human-readable
    explanation.
    """

    code: str
    message: str

    def __str__(self) -> str:  # pragma: no cover — trivial
        return f"{self.code}: {self.message}"


class IdentityFieldsMissing(DomainError):
    """PRE.002 of CMD.MINT_ANCHOR — required identity fields are missing."""

    def __init__(self, missing: list[str]) -> None:
        super().__init__(
            code="IDENTITY_FIELDS_MISSING",
            message=f"Missing required identity fields: {', '.join(missing)}",
        )


class CallerSuppliedInternalId(DomainError):
    """INV.BEN.001 — server is the only legitimate minter of internal_id."""

    def __init__(self) -> None:
        super().__init__(
            code="CALLER_SUPPLIED_INTERNAL_ID",
            message="internal_id is server-minted; the request must not carry one.",
        )


class AnchorNotFound(DomainError):
    """GET / lifecycle commands — no anchor matches the given internal_id."""

    def __init__(self, internal_id: str) -> None:
        super().__init__(
            code="ANCHOR_NOT_FOUND",
            message=f"No anchor found for internal_id={internal_id}.",
        )


class AnchorArchived(DomainError):
    """INV.BEN.004 — UPDATE rejected when anchor is in ARCHIVED state.

    Per commands.yaml::CMD.UPDATE_ANCHOR.errors.ANCHOR_ARCHIVED — caller must
    RESTORE first.
    """

    def __init__(self, internal_id: str) -> None:
        super().__init__(
            code="ANCHOR_ARCHIVED",
            message=(
                f"Anchor {internal_id} is ARCHIVED; UPDATE is not accepted "
                "in this state. Issue RESTORE first."
            ),
        )


class AnchorPseudonymised(DomainError):
    """INV.BEN.006 — UPDATE rejected when anchor is in the terminal
    PSEUDONYMISED state (GDPR Art. 17 erasure). Irreversible.
    """

    def __init__(self, internal_id: str) -> None:
        super().__init__(
            code="ANCHOR_PSEUDONYMISED",
            message=(
                f"Anchor {internal_id} is PSEUDONYMISED — terminal state, "
                "no further mutation is accepted."
            ),
        )


class NoFieldsToUpdate(DomainError):
    """commands.yaml::CMD.UPDATE_ANCHOR.errors.NO_FIELDS_TO_UPDATE — the
    effective payload (after stripping ``command_id``) carries no field to
    mutate, so the command is a no-op. We refuse it so callers don't
    mistake a no-op for a successful application.
    """

    def __init__(self) -> None:
        super().__init__(
            code="NO_FIELDS_TO_UPDATE",
            message="The UPDATE payload carries no mutable field.",
        )


class InternalIdImmutable(DomainError):
    """INV.BEN.002 — internal_id is immutable. Any attempt to mutate it via
    UPDATE / ARCHIVE / RESTORE / PSEUDONYMISE is rejected. In practice the
    presentation layer never lets a body-level ``internal_id`` reach the
    aggregate (it is a path parameter, not a body field), but the aggregate
    raises this as a defense-in-depth guard.
    """

    def __init__(self) -> None:
        super().__init__(
            code="INTERNAL_ID_IMMUTABLE",
            message=(
                "internal_id is immutable for the lifetime of the anchor "
                "(INV.BEN.002)."
            ),
        )
