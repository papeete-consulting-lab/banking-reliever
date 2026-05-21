"""FastAPI routes — one per query operation declared in
``process/BNK.RLVR.CAP.SUP.002.BEN/api.yaml``:

* ``GET /anchors/{internal_id}``         — QRY.GET_ANCHOR
* ``GET /anchors/{internal_id}/history`` — QRY.GET_ANCHOR_HISTORY

Both honour the ETag / 304 contract and the ``max-age`` declared by the
read-models.yaml (60s for getAnchor, 0s for getAnchorHistory).

``404`` is returned for unknown ``internal_id`` per ADR-TECH-STRAT-003.

When ``RELIEVER_STUB_HTTP_ACTIVE=false`` the query half short-circuits
all routes (except ``/health``) to ``503``.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from .fixture_store import FixtureNotFound

log = structlog.get_logger(__name__)

router = APIRouter(tags=["anchors"])


def _ensure_http_active(request: Request) -> None:
    settings = request.app.state.settings
    if not settings.stub_http_active:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STUB_HTTP_ACTIVE=false — query half is disabled",
        )


@router.get("/anchors/{internal_id}")
async def get_anchor(
    internal_id: str,
    request: Request,
    response: Response,
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
) -> dict:
    """QRY.GET_ANCHOR — canned BeneficiaryAnchor (PII null when PSEUDONYMISED)."""
    _ensure_http_active(request)
    store = request.app.state.fixture_store
    try:
        anchor = store.get_anchor(internal_id)
    except FixtureNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ANCHOR_NOT_FOUND"
        )

    etag = store.anchor_etag(internal_id)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "max-age=60"

    if if_none_match and if_none_match == etag:
        # Return 304 with no body.
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return {}

    log.info("query.get_anchor", internal_id=internal_id, status=anchor["anchor_status"])
    return anchor


@router.get("/anchors/{internal_id}/history")
async def get_anchor_history(
    internal_id: str,
    request: Request,
    response: Response,
    since_revision: int | None = None,
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
) -> dict:
    """QRY.GET_ANCHOR_HISTORY — PII-free transition rows (audit-friendly)."""
    _ensure_http_active(request)
    store = request.app.state.fixture_store

    if not store.has_anchor(internal_id):
        # We still need to check history even if anchor row is gone (PSEUDONYMISED
        # anchors are present in both stores). For the stub, presence in the
        # anchor store gates history availability.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ANCHOR_NOT_FOUND"
        )

    try:
        history = store.get_history(internal_id, since_revision=since_revision)
    except FixtureNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ANCHOR_NOT_FOUND"
        )

    etag = store.history_etag(internal_id, since_revision=since_revision)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "max-age=0"

    if if_none_match and if_none_match == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return {}

    log.info(
        "query.get_anchor_history",
        internal_id=internal_id,
        rows=len(history["rows"]),
        since_revision=since_revision,
    )
    return history
