"""Use-case handlers — MintAnchorHandler, UpdateAnchorHandler, GetAnchorHandler.

The handlers are framework-agnostic; FastAPI invokes them from the
presentation routers via DI.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from uuid_extensions import uuid7

from ..domain.aggregate import IdentityAnchor
from ..domain.errors import (
    AnchorAlreadyPseudonymised,
    AnchorArchived,
    AnchorNotFound,
    AnchorPseudonymised,
    DomainError,
    NoFieldsToUpdate,
    RightExerciseIdInvalid,
)
from ..domain.events import (
    AnchorMinted,
    AnchorPseudonymised as AnchorPseudonymisedEvent,
    AnchorUpdated,
    TransitionEvent,
)
from ..domain.value_objects import Actor, ClientRequestId, RightExerciseId
from .dto import (
    BeneficiaryAnchorDto,
    MintAnchorCommandDto,
    PseudonymiseAnchorCommandDto,
    UpdateAnchorCommandDto,
)
from .ports import (
    AnchorDirectoryReader,
    AnchorHistoryReader,
    SchemaValidator,
    UnitOfWorkFactory,
)

# Bus topology — derived verbatim from process/BNK.RLVR.CAP.SUP.002.BEN/bus.yaml.
EXCHANGE_NAME = "sup.002.ben-events"
RVT_EVENT_NAME = "BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED"
BUSINESS_EVENT_NAME = "BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED"
ROUTING_KEY = f"{BUSINESS_EVENT_NAME}.{RVT_EVENT_NAME}"
SCHEMA_ID = "https://reliever.banking/process/BNK.RLVR.CAP.SUP.002.BEN/schemas/BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json"
SCHEMA_VERSION = "0.1.0"
EMITTING_CAPABILITY = "BNK.RLVR.CAP.SUP.002.BEN"

# Idempotency scopes — one per command kind so different commands sharing
# the same key (in the unlikely chance) do not collide.
IDEMPOTENCY_SCOPE_MINT = "MINT_ANCHOR"
IDEMPOTENCY_SCOPE_UPDATE = "UPDATE_ANCHOR"
IDEMPOTENCY_SCOPE_PSEUDONYMISE = "PSEUDONYMISE_ANCHOR"


@dataclass(frozen=True, slots=True)
class MintResult:
    """Result of CMD.MINT_ANCHOR. ``http_status`` is 201 for a fresh mint and
    200 for an idempotent re-call (REQUEST_ALREADY_PROCESSED).
    """

    anchor: BeneficiaryAnchorDto
    http_status: int
    idempotent_replay: bool
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateResult:
    """Result of CMD.UPDATE_ANCHOR. ``http_status`` is 200 either way (fresh
    or idempotent re-call); ``idempotent_replay`` discriminates so the
    presentation layer can populate ``error_code`` consistently.
    """

    anchor: BeneficiaryAnchorDto
    http_status: int
    idempotent_replay: bool
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class PseudonymiseResult:
    """Result of CMD.PSEUDONYMISE_ANCHOR. ``http_status`` is 200 (fresh or
    idempotent re-call); ``idempotent_replay`` discriminates so the
    presentation layer can populate ``error_code`` consistently.

    The anchor DTO has the four PII fields nulled — the canonical PSEUDONYMISED
    shape per BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json.
    """

    anchor: BeneficiaryAnchorDto
    http_status: int
    idempotent_replay: bool
    error_code: str | None = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _mint_uuidv7() -> str:
    return str(uuid7())


def _build_rvt_payload(event: TransitionEvent, actor: Actor) -> dict[str, Any]:
    """Translate a domain transition event into the wire-format
    ``BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED`` payload.

    Three branches per the canonical RVT schema:
      - MINTED / UPDATED / RESTORED — anchor_status=ACTIVE, PII required.
      - ARCHIVED — anchor_status=ARCHIVED, PII still present (snapshot of
        the last known PII).
      - PSEUDONYMISED — anchor_status=PSEUDONYMISED, four PII fields are
        null, pseudonymized_at + right_exercise_id are set.

    Validated against the canonical JSON Schema before the outbox row is
    written (fail-fast on contract drift).
    """
    if isinstance(event, AnchorPseudonymisedEvent):
        # PSEUDONYMISED branch — four PII fields null, pseudonymized_at and
        # right_exercise_id set, anchor_status=PSEUDONYMISED.
        return {
            "envelope": {
                "message_id": _mint_uuidv7(),
                "schema_version": SCHEMA_VERSION,
                "emitted_at": _now_utc().isoformat(),
                "emitting_capability": EMITTING_CAPABILITY,
                "correlation_id": str(event.internal_id),
                "causation_id": event.command_id,
                "actor": actor.to_dict(),
            },
            "internal_id": str(event.internal_id),
            "last_name": None,
            "first_name": None,
            "date_of_birth": None,
            "contact_details": None,
            "anchor_status": "PSEUDONYMISED",
            "creation_date": event.creation_date.isoformat(),
            "pseudonymized_at": event.pseudonymized_at.isoformat(),
            "revision": event.revision,
            "transition_kind": "PSEUDONYMISED",
            "command_id": event.command_id,
            "right_exercise_id": event.right_exercise_id,
            "occurred_at": event.occurred_at.isoformat(),
        }

    # MINTED / UPDATED branches (ARCHIVED / RESTORED land with TASK-004).
    payload: dict[str, Any] = {
        "envelope": {
            "message_id": _mint_uuidv7(),
            "schema_version": SCHEMA_VERSION,
            "emitted_at": _now_utc().isoformat(),
            "emitting_capability": EMITTING_CAPABILITY,
            "correlation_id": str(event.internal_id),  # anchor-scoped correlation
            "causation_id": event.command_id,
            "actor": actor.to_dict(),
        },
        "internal_id": str(event.internal_id),
        "last_name": event.last_name,
        "first_name": event.first_name,
        "date_of_birth": event.date_of_birth.isoformat(),
        "contact_details": event.contact_details.to_dict() if event.contact_details else None,
        "anchor_status": "ACTIVE",  # MINTED/UPDATED/RESTORED branch is always ACTIVE
        "creation_date": event.creation_date.isoformat(),
        "pseudonymized_at": None,
        "revision": event.revision,
        "transition_kind": event.transition_kind,
        "command_id": event.command_id,
        "right_exercise_id": None,
        "occurred_at": event.occurred_at.isoformat(),
    }
    return payload


# ─── CMD.MINT_ANCHOR ───────────────────────────────────────────────────


class MintAnchorHandler:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        rvt_validator: SchemaValidator,
    ) -> None:
        self._uow_factory = uow_factory
        self._rvt_validator = rvt_validator

    async def handle(self, cmd: MintAnchorCommandDto) -> MintResult:
        scope = IDEMPOTENCY_SCOPE_MINT

        # ─── Idempotency check (INV.BEN.008) ──────────────────────────
        async with self._uow_factory() as uow:
            prior = await uow.idempotency.get(scope=scope, key=cmd.client_request_id)
            if prior is not None:
                # Idempotent replay — return the original anchor.
                stored: dict[str, Any] = prior["response_body"]
                return MintResult(
                    anchor=_deserialize_anchor(stored),
                    http_status=200,
                    idempotent_replay=True,
                    error_code="REQUEST_ALREADY_PROCESSED",
                )

        # ─── Fresh mint ───────────────────────────────────────────────
        async with self._uow_factory() as uow:
            # Re-check inside the transaction — defends against the very
            # narrow race where two POSTs arrive simultaneously with the
            # same client_request_id.
            prior = await uow.idempotency.get(scope=scope, key=cmd.client_request_id)
            if prior is not None:
                stored = prior["response_body"]
                await uow.rollback()
                return MintResult(
                    anchor=_deserialize_anchor(stored),
                    http_status=200,
                    idempotent_replay=True,
                    error_code="REQUEST_ALREADY_PROCESSED",
                )

            # Provision the per-anchor DEK first — the anchor row's
            # crypto_key_id FK references it. Same transaction so a rollback
            # cleans both up.
            crypto_key_id = _mint_uuidv7()
            await uow.crypto_keys.provision(crypto_key_id=crypto_key_id)

            anchor = IdentityAnchor.mint(
                client_request_id=ClientRequestId(cmd.client_request_id),
                last_name=cmd.last_name,
                first_name=cmd.first_name,
                date_of_birth=cmd.date_of_birth,
                contact_details=cmd.contact_details,
                actor=cmd.actor,
                crypto_key_id=crypto_key_id,
            )
            # IdentityAnchor.mint() raises IdentityFieldsMissing on PRE.002.

            await uow.anchors.insert(anchor)

            events = anchor.pull_pending_events()
            assert len(events) == 1, "AGG must emit exactly one event per transition (INV.BEN.007)"
            event = events[0]
            assert isinstance(event, AnchorMinted)

            # Validate the wire-format payload BEFORE writing the outbox row.
            payload = _build_rvt_payload(event, cmd.actor)
            self._rvt_validator.validate_payload(payload)

            message_id = payload["envelope"]["message_id"]
            await uow.outbox.append(
                message_id=message_id,
                correlation_id=str(event.internal_id),
                causation_id=event.command_id,
                schema_id=SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                routing_key=ROUTING_KEY,
                exchange=EXCHANGE_NAME,
                occurred_at=event.occurred_at,
                actor=cmd.actor.to_dict(),
                payload=payload,
            )

            # Idempotency record — must be in the same transaction so the
            # row is durable iff the anchor row is.
            dto = _anchor_to_dto(anchor)
            await uow.idempotency.remember(
                scope=scope,
                key=cmd.client_request_id,
                internal_id=str(anchor.internal_id),
                response_body=dto.to_dict(),
                response_code=201,
            )

            await uow.commit()
            return MintResult(anchor=dto, http_status=201, idempotent_replay=False)


# ─── CMD.UPDATE_ANCHOR ─────────────────────────────────────────────────


class UpdateAnchorHandler:
    """Handles CMD.SUP.002.BEN.UPDATE_ANCHOR.

    The handler:

      1. Validates the wire payload against
         ``CMD.SUP.002.BEN.UPDATE_ANCHOR.schema.json`` (done at the
         presentation boundary; the handler trusts the DTO).
      2. Looks up the idempotency table keyed on
         ``(UPDATE_ANCHOR, command_id)``; on hit returns the prior
         snapshot with ``COMMAND_ALREADY_PROCESSED``.
      3. Loads the aggregate by ``internal_id``; raises
         ``AnchorNotFound`` (→ 404) if absent.
      4. Calls ``IdentityAnchor.update(...)`` which enforces the
         lifecycle guards and the sticky-PII merge.
      5. Builds and validates the wire RVT, writes the outbox row.
      6. Persists the aggregate (UPDATE … WHERE internal_id) and the
         idempotency row in the SAME transaction (atomic outbox).
    """

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        rvt_validator: SchemaValidator,
    ) -> None:
        self._uow_factory = uow_factory
        self._rvt_validator = rvt_validator

    async def handle(self, cmd: UpdateAnchorCommandDto) -> UpdateResult:
        scope = IDEMPOTENCY_SCOPE_UPDATE

        # ─── Idempotency check (INV.BEN.008) ──────────────────────────
        async with self._uow_factory() as uow:
            prior = await uow.idempotency.get(scope=scope, key=cmd.command_id)
            if prior is not None:
                stored: dict[str, Any] = prior["response_body"]
                return UpdateResult(
                    anchor=_deserialize_anchor(stored),
                    http_status=200,
                    idempotent_replay=True,
                    error_code="COMMAND_ALREADY_PROCESSED",
                )

        # ─── Fresh update ─────────────────────────────────────────────
        async with self._uow_factory() as uow:
            # Re-check inside the transaction — race defence.
            prior = await uow.idempotency.get(scope=scope, key=cmd.command_id)
            if prior is not None:
                stored = prior["response_body"]
                await uow.rollback()
                return UpdateResult(
                    anchor=_deserialize_anchor(stored),
                    http_status=200,
                    idempotent_replay=True,
                    error_code="COMMAND_ALREADY_PROCESSED",
                )

            # Load the aggregate. Missing → 404 ANCHOR_NOT_FOUND.
            anchor = await uow.anchors.get(cmd.internal_id)
            if anchor is None:
                raise AnchorNotFound(cmd.internal_id)

            # Apply the command. Raises:
            #   - AnchorArchived (→ 409)
            #   - AnchorPseudonymised (→ 409)
            #   - NoFieldsToUpdate (→ 400)
            #   - InternalIdImmutable (→ 400, defence-in-depth)
            anchor.update(
                command_id=cmd.command_id,
                fields=cmd.fields,
                actor=cmd.actor,
            )

            events = anchor.pull_pending_events()
            assert len(events) == 1, "AGG must emit exactly one event per transition (INV.BEN.007)"
            event = events[0]
            assert isinstance(event, AnchorUpdated)

            payload = _build_rvt_payload(event, cmd.actor)
            self._rvt_validator.validate_payload(payload)

            await uow.anchors.update(anchor)

            message_id = payload["envelope"]["message_id"]
            await uow.outbox.append(
                message_id=message_id,
                correlation_id=str(event.internal_id),
                causation_id=event.command_id,
                schema_id=SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                routing_key=ROUTING_KEY,
                exchange=EXCHANGE_NAME,
                occurred_at=event.occurred_at,
                actor=cmd.actor.to_dict(),
                payload=payload,
            )

            dto = _anchor_to_dto(anchor)
            await uow.idempotency.remember(
                scope=scope,
                key=cmd.command_id,
                internal_id=str(anchor.internal_id),
                response_body=dto.to_dict(),
                response_code=200,
            )

            await uow.commit()
            return UpdateResult(anchor=dto, http_status=200, idempotent_replay=False)


# ─── CMD.PSEUDONYMISE_ANCHOR ───────────────────────────────────────────


class PseudonymiseAnchorHandler:
    """Handles CMD.SUP.002.BEN.PSEUDONYMISE_ANCHOR.

    The handler:

      1. Validates the wire payload against
         ``CMD.SUP.002.BEN.PSEUDONYMISE_ANCHOR.schema.json`` at the
         presentation boundary; the handler trusts the DTO.
      2. Looks up the idempotency table keyed on
         ``(PSEUDONYMISE_ANCHOR, command_id)``; on hit returns the prior
         snapshot with ``COMMAND_ALREADY_PROCESSED`` and DOES NOT re-run
         the crypto-shred (PRE.003 / INV.BEN.008).
      3. Loads the aggregate by ``internal_id``; raises ``AnchorNotFound``
         (→ 404) if absent.
      4. Calls ``IdentityAnchor.pseudonymise(...)`` which enforces the
         terminal-state guard (INV.BEN.006) and the crypto-shred
         post-condition (PII fields wiped on the value object,
         crypto_key_id severed).
      5. Persists the aggregate (UPDATE ... WHERE internal_id) AND deletes
         the DEK row from anchor_crypto_keys AND writes the outbox row in
         the SAME transaction (atomic shredding + atomic outbox per
         ADR-TECH-STRAT-001 Rule 3).
      6. Validates the wire RVT against the canonical schema (fail-fast on
         contract drift, exercises the if/then PSEUDONYMISED branch).
    """

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        rvt_validator: SchemaValidator,
    ) -> None:
        self._uow_factory = uow_factory
        self._rvt_validator = rvt_validator

    async def handle(self, cmd: PseudonymiseAnchorCommandDto) -> PseudonymiseResult:
        scope = IDEMPOTENCY_SCOPE_PSEUDONYMISE

        # ─── Idempotency check (INV.BEN.008) ──────────────────────────
        async with self._uow_factory() as uow:
            prior = await uow.idempotency.get(scope=scope, key=cmd.command_id)
            if prior is not None:
                stored: dict[str, Any] = prior["response_body"]
                return PseudonymiseResult(
                    anchor=_deserialize_anchor(stored),
                    http_status=200,
                    idempotent_replay=True,
                    error_code="COMMAND_ALREADY_PROCESSED",
                )

        # ─── Fresh pseudonymisation ───────────────────────────────────
        async with self._uow_factory() as uow:
            # Re-check inside the transaction — race defence (two POSTs
            # arriving with the same command_id simultaneously).
            prior = await uow.idempotency.get(scope=scope, key=cmd.command_id)
            if prior is not None:
                stored = prior["response_body"]
                await uow.rollback()
                return PseudonymiseResult(
                    anchor=_deserialize_anchor(stored),
                    http_status=200,
                    idempotent_replay=True,
                    error_code="COMMAND_ALREADY_PROCESSED",
                )

            # Load the aggregate. Missing → 404 ANCHOR_NOT_FOUND.
            anchor = await uow.anchors.get(cmd.internal_id)
            if anchor is None:
                raise AnchorNotFound(cmd.internal_id)

            # Build the validated RightExerciseId VO. Raises ValueError on
            # ill-formed UUIDv7; surface as RightExerciseIdInvalid (400).
            try:
                right_exercise_id_vo = RightExerciseId(cmd.right_exercise_id)
            except ValueError as exc:
                raise RightExerciseIdInvalid(cmd.right_exercise_id) from exc

            # Apply the command. Raises:
            #   - AnchorAlreadyPseudonymised (→ 409 terminal state)
            #   - RightExerciseIdInvalid (→ 400 defence-in-depth)
            anchor.pseudonymise(
                command_id=cmd.command_id,
                right_exercise_id=right_exercise_id_vo,
                reason=cmd.reason,
                actor=cmd.actor,
            )

            events = anchor.pull_pending_events()
            assert len(events) == 1, "AGG must emit exactly one event per transition (INV.BEN.007)"
            event = events[0]
            assert isinstance(event, AnchorPseudonymisedEvent)

            # Validate the wire-format payload BEFORE writing the outbox row
            # — this exercises the if/then PSEUDONYMISED branch of the
            # canonical RVT schema.
            payload = _build_rvt_payload(event, cmd.actor)
            self._rvt_validator.validate_payload(payload)

            # Persist the aggregate (PII columns set to NULL, crypto_key_id
            # severed, anchor_status=PSEUDONYMISED) and IN THE SAME
            # TRANSACTION delete the DEK row → the at-rest ciphertext
            # becomes unrecoverable (crypto-shredding observable
            # post-condition).
            await uow.anchors.update(anchor)
            shredded_key_id = anchor.pull_shredded_crypto_key_id()
            if shredded_key_id is not None:
                await uow.crypto_keys.shred(crypto_key_id=shredded_key_id)

            message_id = payload["envelope"]["message_id"]
            await uow.outbox.append(
                message_id=message_id,
                correlation_id=str(event.internal_id),
                causation_id=event.command_id,
                schema_id=SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                routing_key=ROUTING_KEY,
                exchange=EXCHANGE_NAME,
                occurred_at=event.occurred_at,
                actor=cmd.actor.to_dict(),
                payload=payload,
            )

            dto = _anchor_to_dto(anchor)
            await uow.idempotency.remember(
                scope=scope,
                key=cmd.command_id,
                internal_id=str(anchor.internal_id),
                response_body=dto.to_dict(),
                response_code=200,
            )

            await uow.commit()
            return PseudonymiseResult(
                anchor=dto, http_status=200, idempotent_replay=False
            )


# ─── Helpers ───────────────────────────────────────────────────────────


def _anchor_to_dto(anchor: IdentityAnchor) -> BeneficiaryAnchorDto:
    return BeneficiaryAnchorDto(
        internal_id=str(anchor.internal_id),
        last_name=anchor.pii.last_name,
        first_name=anchor.pii.first_name,
        date_of_birth=anchor.pii.date_of_birth,
        contact_details=(
            anchor.pii.contact_details.to_dict() if anchor.pii.contact_details else None
        ),
        anchor_status=anchor.anchor_status,
        creation_date=anchor.creation_date,
        pseudonymized_at=anchor.pseudonymized_at,
        revision=anchor.revision,
    )


def _deserialize_anchor(stored: dict[str, Any]) -> BeneficiaryAnchorDto:
    """Reconstruct a BeneficiaryAnchorDto from a stored idempotency response."""
    from datetime import date as _date

    creation_date = _date.fromisoformat(stored["creation_date"]) if stored.get("creation_date") else None
    date_of_birth = _date.fromisoformat(stored["date_of_birth"]) if stored.get("date_of_birth") else None
    pseudonymized_at = (
        datetime.fromisoformat(stored["pseudonymized_at"])
        if stored.get("pseudonymized_at")
        else None
    )
    assert creation_date is not None, "creation_date is required in stored payload"
    return BeneficiaryAnchorDto(
        internal_id=stored["internal_id"],
        last_name=stored.get("last_name"),
        first_name=stored.get("first_name"),
        date_of_birth=date_of_birth,
        contact_details=stored.get("contact_details"),
        anchor_status=stored["anchor_status"],
        creation_date=creation_date,
        pseudonymized_at=pseudonymized_at,
        revision=stored["revision"],
    )


# ─── QRY.GET_ANCHOR ────────────────────────────────────────────────────


class GetAnchorHandler:
    def __init__(self, *, reader: AnchorDirectoryReader) -> None:
        self._reader = reader

    async def handle(self, internal_id: str) -> BeneficiaryAnchorDto:
        # Defensive — the presentation layer will already have validated the
        # UUIDv7 format. Reject obviously malformed ids here too.
        try:
            uuid.UUID(internal_id)
        except ValueError as exc:
            raise AnchorNotFound(internal_id) from exc

        row = await self._reader.get(internal_id)
        if row is None:
            raise AnchorNotFound(internal_id)
        return _row_to_dto(row)


# ─── QRY.GET_ANCHOR_HISTORY (TASK-006) ─────────────────────────────────


@dataclass(frozen=True, slots=True)
class AnchorHistoryRow:
    """One transition entry in the audit-trail response.

    Mirrors the seven fields declared in
    ``read-models.yaml.PRJ.ANCHOR_HISTORY.fields``. PII-free by
    construction — no last_name / first_name / date_of_birth /
    contact_details.
    """

    internal_id: str
    revision: int
    transition_kind: str
    command_id: str | None
    right_exercise_id: str | None
    actor: dict[str, Any]
    occurred_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "internal_id": self.internal_id,
            "revision": self.revision,
            "transition_kind": self.transition_kind,
            "command_id": self.command_id,
            "right_exercise_id": self.right_exercise_id,
            "actor": self.actor,
            "occurred_at": self.occurred_at.isoformat()
            if isinstance(self.occurred_at, datetime)
            else self.occurred_at,
        }


@dataclass(frozen=True, slots=True)
class AnchorHistoryResult:
    """Wraps the ordered rows of the projection lookup. The presentation
    layer derives the ETag from the underlying raw rows so the
    bytes-on-the-wire are stable across calls.
    """

    rows: list[AnchorHistoryRow]
    raw_rows: list[dict[str, Any]]


class GetAnchorHistoryHandler:
    """Use-case handler for ``QRY.GET_ANCHOR_HISTORY`` —
    ``GET /anchors/{internal_id}/history`` per api.yaml.

    Returns rows ordered by ``revision`` ascending (the order in which
    they were emitted by the aggregate). The ``since_revision`` filter
    is strict — rows with ``revision > since_revision`` only.
    """

    def __init__(self, *, reader: AnchorHistoryReader) -> None:
        self._reader = reader

    async def handle(
        self,
        *,
        internal_id: str,
        since_revision: int | None = None,
    ) -> AnchorHistoryResult:
        # Defensive UUIDv7 parse — the presentation layer already vets
        # the format; reject obviously malformed ids here too.
        try:
            uuid.UUID(internal_id)
        except ValueError as exc:
            raise AnchorNotFound(internal_id) from exc

        rows = await self._reader.list(
            internal_id=internal_id, since_revision=since_revision
        )
        # 404 ONLY when the anchor itself has zero history. A non-empty
        # history with ``since_revision`` filtering down to zero rows
        # returns 200 with an empty list (the caller polled past the
        # tail).
        if since_revision is None and not rows:
            raise AnchorNotFound(internal_id)
        if since_revision is not None:
            # Confirm the anchor exists at all — we re-query without the
            # filter only when the filter yielded nothing.
            if not rows:
                # One extra round-trip is cheap (audit traffic is tiny)
                # and keeps the 404 invariant exact.
                base = await self._reader.list(internal_id=internal_id)
                if not base:
                    raise AnchorNotFound(internal_id)

        typed = [
            AnchorHistoryRow(
                internal_id=str(r["internal_id"]),
                revision=int(r["revision"]),
                transition_kind=str(r["transition_kind"]),
                command_id=str(r["command_id"]) if r.get("command_id") else None,
                right_exercise_id=str(r["right_exercise_id"])
                if r.get("right_exercise_id")
                else None,
                actor=r["actor"] if isinstance(r["actor"], dict)
                else json.loads(r["actor"]),
                occurred_at=r["occurred_at"],
            )
            for r in rows
        ]
        return AnchorHistoryResult(rows=typed, raw_rows=rows)


def _row_to_dto(row: dict[str, Any]) -> BeneficiaryAnchorDto:
    cd = row.get("contact_details")
    if isinstance(cd, str):
        cd = json.loads(cd)
    return BeneficiaryAnchorDto(
        internal_id=str(row["internal_id"]),
        last_name=row.get("last_name"),
        first_name=row.get("first_name"),
        date_of_birth=row.get("date_of_birth"),
        contact_details=cd,
        anchor_status=row["anchor_status"],
        creation_date=row["creation_date"],
        pseudonymized_at=row.get("pseudonymized_at"),
        revision=row["revision"],
    )


__all__ = [
    "MintAnchorHandler",
    "UpdateAnchorHandler",
    "PseudonymiseAnchorHandler",
    "GetAnchorHandler",
    "GetAnchorHistoryHandler",
    "AnchorHistoryRow",
    "AnchorHistoryResult",
    "MintResult",
    "UpdateResult",
    "PseudonymiseResult",
    "EXCHANGE_NAME",
    "ROUTING_KEY",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "EMITTING_CAPABILITY",
    "IDEMPOTENCY_SCOPE_MINT",
    "IDEMPOTENCY_SCOPE_UPDATE",
    "IDEMPOTENCY_SCOPE_PSEUDONYMISE",
]
