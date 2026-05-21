"""Pydantic models for the HTTP request/response bodies.

These mirror the JSON Schema canonical shape; the JSON Schema validation
remains the authoritative check (it catches things Pydantic doesn't, like
the conditional ``allOf`` branches on the RVT). Pydantic gives the
FastAPI OpenAPI doc its body shapes.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PostalAddressModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line1: str | None = None
    line2: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str | None = None


class ContactDetailsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = None
    phone: str | None = None
    postal_address: PostalAddressModel | None = None


class MintAnchorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_request_id: str = Field(
        ...,
        description="UUIDv7 — caller-supplied idempotency anchor (30-day window).",
    )
    last_name: str = Field(..., min_length=1, max_length=200)
    first_name: str = Field(..., min_length=1, max_length=200)
    date_of_birth: date
    contact_details: ContactDetailsModel | None = None


# ─── CMD.UPDATE_ANCHOR ─────────────────────────────────────────────────
#
# Note on sticky-PII (INV.BEN.003): the canonical wire schema is
# CMD.SUP.002.BEN.UPDATE_ANCHOR.schema.json — additionalProperties=false +
# minProperties=2 (command_id + at least one other). To preserve the
# absent-vs-explicit-null distinction at the application boundary, the
# presentation layer DOES NOT parse the body into this Pydantic model —
# it inspects the raw dict and builds an UpdateFields VO directly. The
# Pydantic model here exists ONLY to generate accurate OpenAPI documentation.


class _ContactDetailsUpdateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = None
    phone: str | None = None
    postal_address: PostalAddressModel | None = None


class UpdateAnchorRequest(BaseModel):
    """OpenAPI documentation only. Sticky-PII parsing uses the raw dict."""

    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(
        ..., description="UUIDv7 — caller-supplied command id (30-day idempotency window)."
    )
    last_name: str | None = Field(default=None, min_length=1, max_length=200)
    first_name: str | None = Field(default=None, min_length=1, max_length=200)
    date_of_birth: date | None = None
    contact_details: _ContactDetailsUpdateModel | None = None


class BeneficiaryAnchorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    internal_id: str
    last_name: str | None
    first_name: str | None
    date_of_birth: date | None
    contact_details: dict[str, Any] | None
    anchor_status: str
    creation_date: date
    pseudonymized_at: datetime | None
    revision: int


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    anchor: BeneficiaryAnchorResponse | None = None  # populated for idempotent replay
