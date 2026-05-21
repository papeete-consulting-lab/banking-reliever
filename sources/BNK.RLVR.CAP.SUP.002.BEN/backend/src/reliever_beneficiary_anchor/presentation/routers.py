"""FastAPI routers — wire the api.yaml contract literally.

api_binding alignment:
  POST   /anchors                — CMD.MINT_ANCHOR
  PATCH  /anchors/{internal_id}  — CMD.UPDATE_ANCHOR
  GET    /anchors/{internal_id}  — QRY.GET_ANCHOR
  GET    /health                 — liveness
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import jsonschema
import structlog
from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse

from ..application.dto import (
    ContactDetailsUpdate,
    MintAnchorCommandDto,
    UNSET,
    UpdateAnchorCommandDto,
    UpdateFields,
)
from ..application.handlers import (
    GetAnchorHandler,
    MintAnchorHandler,
    MintResult,
    UpdateAnchorHandler,
    UpdateResult,
)
from ..domain.errors import (
    AnchorArchived,
    AnchorNotFound,
    AnchorPseudonymised,
    CallerSuppliedInternalId,
    DomainError,
    IdentityFieldsMissing,
    InternalIdImmutable,
    NoFieldsToUpdate,
)
from ..domain.value_objects import ContactDetails, PostalAddress
from ..infrastructure.persistence.projection import compute_etag
from ..infrastructure.security.jwt import actor_from_bearer
from .dependencies import AppState, get_state
from .dto import (
    BeneficiaryAnchorResponse,
    ContactDetailsModel,
    ErrorResponse,
    MintAnchorRequest,
    UpdateAnchorRequest,
)

log = structlog.get_logger()
router = APIRouter()

# RFC-9562 §5.7 — UUIDv7 regex; aligned with the JSON Schema $defs/Uuidv7.
_UUIDV7_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


# ─── Health ────────────────────────────────────────────────────────────


@router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ─── CMD.MINT_ANCHOR ───────────────────────────────────────────────────


@router.post(
    "/anchors",
    tags=["commands"],
    summary="Mint a new beneficiary identity anchor",
    response_model=None,
    responses={
        201: {"model": BeneficiaryAnchorResponse, "description": "Anchor minted."},
        200: {
            "model": BeneficiaryAnchorResponse,
            "description": "Idempotent re-call — returns the original anchor (REQUEST_ALREADY_PROCESSED).",
        },
        400: {"model": ErrorResponse, "description": "IDENTITY_FIELDS_MISSING or schema violation."},
    },
)
async def mint_anchor(
    body: dict[str, Any],
    request: Request,
    authorization: str | None = Header(default=None),
    state: AppState = Depends(get_state),
) -> Response:
    # ─── INV.BEN.001 — reject caller-supplied internal_id ──────────────
    if "internal_id" in body:
        raise CallerSuppliedInternalId()

    # ─── JSON Schema validation (canonical contract) ───────────────────
    try:
        state.mint_validator.validate_payload(body)
    except jsonschema.ValidationError as exc:
        # Map the schema error to the canonical IDENTITY_FIELDS_MISSING
        # code when the failure is on a required identity field; otherwise
        # surface a generic INVALID_PAYLOAD.
        missing = [str(p) for p in exc.path]
        msg = exc.message
        # ``required`` violations have an empty path; sniff the message
        # for the missing-field name to map to IDENTITY_FIELDS_MISSING.
        identity_fields = {"last_name", "first_name", "date_of_birth"}
        if exc.validator == "required":
            tokens = re.findall(r"'(\w+)'", msg)
            missing = [t for t in tokens if t in identity_fields]
            if missing:
                err = IdentityFieldsMissing(missing)
                return JSONResponse(
                    status_code=400,
                    content={"error_code": err.code, "message": err.message},
                )
        return JSONResponse(
            status_code=400,
            content={"error_code": "INVALID_PAYLOAD", "message": msg},
        )

    # ─── Pydantic parse (typed shape) ──────────────────────────────────
    try:
        req = MintAnchorRequest.model_validate(body)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=400,
            content={"error_code": "INVALID_PAYLOAD", "message": str(exc)},
        )

    # ─── Build the command DTO ────────────────────────────────────────
    contact = _to_domain_contact(req.contact_details)
    actor = actor_from_bearer(authorization)
    cmd = MintAnchorCommandDto(
        client_request_id=req.client_request_id,
        last_name=req.last_name,
        first_name=req.first_name,
        date_of_birth=req.date_of_birth,
        contact_details=contact,
        actor=actor,
    )

    # ─── Handle ────────────────────────────────────────────────────────
    try:
        result: MintResult = await state.mint_handler.handle(cmd)
    except IdentityFieldsMissing as exc:
        return JSONResponse(
            status_code=400,
            content={"error_code": exc.code, "message": exc.message},
        )

    payload = result.anchor.to_dict()
    if result.idempotent_replay:
        body_out = {"error_code": result.error_code, "anchor": payload}
        return JSONResponse(status_code=200, content=body_out)
    return JSONResponse(status_code=201, content=payload)


def _to_domain_contact(model: ContactDetailsModel | None) -> ContactDetails | None:
    if model is None:
        return None
    postal = model.postal_address
    return ContactDetails(
        email=model.email,
        phone=model.phone,
        postal_address=PostalAddress(
            line1=postal.line1,
            line2=postal.line2,
            postal_code=postal.postal_code,
            city=postal.city,
            country=postal.country,
        ) if postal else None,
    )


# ─── CMD.UPDATE_ANCHOR ─────────────────────────────────────────────────


@router.patch(
    "/anchors/{internal_id}",
    tags=["commands"],
    summary="Apply a partial PII update to an anchor (sticky-PII; INV.BEN.003)",
    response_model=None,
    responses={
        200: {
            "model": BeneficiaryAnchorResponse,
            "description": (
                "Update applied. On an idempotent re-call (COMMAND_ALREADY_PROCESSED) "
                "the body wraps the prior anchor: "
                "`{\"error_code\": \"COMMAND_ALREADY_PROCESSED\", \"anchor\": {...}}`. "
                "On a fresh apply the body is the BeneficiaryAnchor shape directly."
            ),
        },
        400: {"model": ErrorResponse, "description": "NO_FIELDS_TO_UPDATE or schema violation."},
        404: {"model": ErrorResponse, "description": "ANCHOR_NOT_FOUND."},
        409: {"model": ErrorResponse, "description": "ANCHOR_ARCHIVED or ANCHOR_PSEUDONYMISED."},
    },
)
async def update_anchor(  # noqa: PLR0911 — explicit error-mapping branches
    internal_id: str,
    body: dict[str, Any],
    request: Request,
    authorization: str | None = Header(default=None),
    state: AppState = Depends(get_state),
) -> Response:
    # ─── Reject ill-formed internal_id (404 per api.yaml policy) ───────
    if not _UUIDV7_RE.match(internal_id):
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "ANCHOR_NOT_FOUND",
                "message": f"No anchor found for internal_id={internal_id}.",
            },
        )

    # ─── INV.BEN.002 — body must NOT carry internal_id ─────────────────
    if "internal_id" in body:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "INTERNAL_ID_IMMUTABLE",
                "message": (
                    "internal_id is the path parameter and is immutable; do "
                    "not carry it in the request body (INV.BEN.002)."
                ),
            },
        )

    # ─── JSON Schema validation (canonical contract) ───────────────────
    try:
        state.update_validator.validate_payload(body)
    except jsonschema.ValidationError as exc:
        msg = exc.message
        # The schema enforces minProperties=2 (command_id + at least one
        # other). When that constraint fires, surface the canonical
        # NO_FIELDS_TO_UPDATE code rather than a generic INVALID_PAYLOAD —
        # it's the same outcome (no mutable field).
        if exc.validator == "minProperties":
            err = NoFieldsToUpdate()
            return JSONResponse(
                status_code=400,
                content={"error_code": err.code, "message": err.message},
            )
        return JSONResponse(
            status_code=400,
            content={"error_code": "INVALID_PAYLOAD", "message": msg},
        )

    # ─── Sticky-PII parse — preserves absent-vs-null distinction ───────
    try:
        fields = _parse_update_fields(body)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error_code": "INVALID_PAYLOAD", "message": str(exc)},
        )

    command_id = body["command_id"]
    actor = actor_from_bearer(authorization)
    cmd = UpdateAnchorCommandDto(
        internal_id=internal_id,
        command_id=command_id,
        fields=fields,
        actor=actor,
    )

    # ─── Handle ────────────────────────────────────────────────────────
    try:
        result: UpdateResult = await state.update_handler.handle(cmd)
    except AnchorNotFound as exc:
        return JSONResponse(
            status_code=404,
            content={"error_code": exc.code, "message": exc.message},
        )
    except AnchorArchived as exc:
        return JSONResponse(
            status_code=409,
            content={"error_code": exc.code, "message": exc.message},
        )
    except AnchorPseudonymised as exc:
        return JSONResponse(
            status_code=409,
            content={"error_code": exc.code, "message": exc.message},
        )
    except NoFieldsToUpdate as exc:
        return JSONResponse(
            status_code=400,
            content={"error_code": exc.code, "message": exc.message},
        )
    except InternalIdImmutable as exc:
        return JSONResponse(
            status_code=400,
            content={"error_code": exc.code, "message": exc.message},
        )

    anchor_payload = result.anchor.to_dict()
    etag = compute_etag(result.anchor.internal_id, result.anchor.revision)
    if result.idempotent_replay:
        body_out = {"error_code": result.error_code, "anchor": anchor_payload}
        return JSONResponse(
            status_code=200,
            content=body_out,
            headers={"ETag": etag},
        )
    return JSONResponse(
        status_code=200,
        content=anchor_payload,
        headers={"ETag": etag, "Cache-Control": "max-age=60"},
    )


def _parse_update_fields(body: dict[str, Any]) -> UpdateFields:
    """Turn the raw request dict into an ``UpdateFields`` carrying the
    sticky-PII semantics.

    Rules:
      * a key absent from ``body`` → ``UNSET`` (no-op)
      * a contact-channel key present with explicit ``null`` → ``None`` (clear)
      * a field key present with a value → the parsed value (replace)

    The wire schema has already validated types and constraints; the
    parser is type-conversion only.
    """
    # last_name / first_name / date_of_birth are REQUIRED-or-absent
    # (the schema rejects null on them via minLength=1 / format=date).
    last_name: Any = body["last_name"] if "last_name" in body else UNSET
    first_name: Any = body["first_name"] if "first_name" in body else UNSET
    dob_raw: Any = body["date_of_birth"] if "date_of_birth" in body else UNSET
    if dob_raw is not UNSET:
        try:
            dob: Any = date.fromisoformat(dob_raw)
        except (TypeError, ValueError) as exc:  # pragma: no cover — schema catches first
            raise ValueError(f"Invalid date_of_birth: {dob_raw!r}") from exc
    else:
        dob = UNSET

    # contact_details has presence + nullability + nested sticky semantics.
    contact_field: Any
    if "contact_details" not in body:
        contact_field = UNSET
    else:
        raw_contact = body["contact_details"]
        if raw_contact is None:
            # Explicit null on the parent — clear ALL three channels at once.
            contact_field = ContactDetailsUpdate(email=None, phone=None, postal_address=None)
        else:
            assert isinstance(raw_contact, dict)
            email: Any = raw_contact["email"] if "email" in raw_contact else UNSET
            phone: Any = raw_contact["phone"] if "phone" in raw_contact else UNSET
            postal_field: Any
            if "postal_address" not in raw_contact:
                postal_field = UNSET
            else:
                raw_postal = raw_contact["postal_address"]
                if raw_postal is None:
                    postal_field = None
                else:
                    postal_field = PostalAddress(
                        line1=raw_postal.get("line1"),
                        line2=raw_postal.get("line2"),
                        postal_code=raw_postal.get("postal_code"),
                        city=raw_postal.get("city"),
                        country=raw_postal.get("country"),
                    )
            contact_field = ContactDetailsUpdate(
                email=email,
                phone=phone,
                postal_address=postal_field,
            )

    return UpdateFields(
        last_name=last_name,
        first_name=first_name,
        date_of_birth=dob,
        contact_details=contact_field,
        attempts_internal_id_mutation=False,  # body-level internal_id already rejected above
    )


# ─── QRY.GET_ANCHOR ────────────────────────────────────────────────────


@router.get(
    "/anchors/{internal_id}",
    tags=["queries"],
    summary="Get an anchor by internal_id",
    response_model=None,
    responses={
        200: {"model": BeneficiaryAnchorResponse},
        304: {"description": "ETag match — body omitted."},
        404: {"model": ErrorResponse, "description": "ANCHOR_NOT_FOUND."},
    },
)
async def get_anchor(
    internal_id: str,
    if_none_match: str | None = Header(default=None),
    state: AppState = Depends(get_state),
) -> Response:
    if not _UUIDV7_RE.match(internal_id):
        # An ill-formed id maps to ANCHOR_NOT_FOUND per the api.yaml contract
        # (we don't expose 422 because the caller can't usefully retry).
        return JSONResponse(
            status_code=404,
            content={"error_code": "ANCHOR_NOT_FOUND",
                     "message": f"No anchor found for internal_id={internal_id}."},
        )

    try:
        dto = await state.get_handler.handle(internal_id)
    except AnchorNotFound as exc:
        return JSONResponse(
            status_code=404,
            content={"error_code": exc.code, "message": exc.message},
        )

    etag = compute_etag(dto.internal_id, dto.revision)
    if if_none_match is not None and _etag_matches(if_none_match, etag):
        # 304 — body omitted but ETag and Cache-Control still set so the
        # client can refresh its TTL.
        return Response(
            status_code=304,
            headers={"ETag": etag, "Cache-Control": "max-age=60"},
        )
    return JSONResponse(
        status_code=200,
        content=dto.to_dict(),
        headers={"ETag": etag, "Cache-Control": "max-age=60"},
    )


def _etag_matches(if_none_match: str, our_etag: str) -> bool:
    """RFC-7232 weak ETag comparison — strip ``W/`` and compare opaque
    values for any of the comma-separated ETags carried by the header.
    """
    def _normalise(t: str) -> str:
        t = t.strip()
        if t.startswith("W/"):
            t = t[2:]
        return t.strip()

    ours = _normalise(our_etag)
    return any(_normalise(t) == ours for t in if_none_match.split(","))


# ─── Domain error handler — uncaught ``DomainError`` → 500 with code ──


def install_exception_handlers(app) -> None:  # noqa: ANN001
    @app.exception_handler(CallerSuppliedInternalId)
    async def _h_caller(_: Request, exc: CallerSuppliedInternalId):
        return JSONResponse(
            status_code=400,
            content={"error_code": exc.code, "message": exc.message},
        )

    @app.exception_handler(DomainError)
    async def _h_domain(_: Request, exc: DomainError):
        log.warning("domain.error", code=exc.code)
        return JSONResponse(
            status_code=400,
            content={"error_code": exc.code, "message": exc.message},
        )


# ``UpdateAnchorRequest`` is re-exported for OpenAPI tooling (the harness
# generator inspects the routers' imports).
__all__ = ["router", "install_exception_handlers", "UpdateAnchorRequest"]
