"""End-to-end integration test for MINT + GET — runs the FastAPI app
in-process against the docker-compose Postgres + RabbitMQ.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from reliever_beneficiary_anchor.presentation.app import create_app

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def client(app_settings, reset_db):
    app = create_app(app_settings)
    # Manually drive the lifespan because httpx.ASGITransport does not.
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


def _crid() -> str:
    return f"018f8e10-eeee-7{uuid.uuid4().hex[1:4]}-8{uuid.uuid4().hex[1:4]}-{uuid.uuid4().hex[:12]}"


def _mint_body(crid: str | None = None) -> dict:
    return {
        "client_request_id": crid or _crid(),
        "last_name": "Dupont",
        "first_name": "Marie",
        "date_of_birth": "1985-06-21",
        "contact_details": {"email": "marie.dupont@example.org"},
    }


async def test_post_anchors_returns_201_with_server_minted_internal_id(client):
    resp = await client.post("/anchors", json=_mint_body())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # UUIDv7 — version=7 nibble.
    assert body["internal_id"][14] == "7"
    assert body["anchor_status"] == "ACTIVE"
    assert body["revision"] == 1
    assert body["last_name"] == "Dupont"


async def test_post_with_caller_supplied_internal_id_is_rejected(client):
    body = _mint_body()
    body["internal_id"] = "018f8e10-bbbb-7000-8000-000000000001"
    resp = await client.post("/anchors", json=body)
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "CALLER_SUPPLIED_INTERNAL_ID"


async def test_post_missing_last_name_returns_400_identity_fields_missing(client):
    body = _mint_body()
    del body["last_name"]
    resp = await client.post("/anchors", json=body)
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "IDENTITY_FIELDS_MISSING"


async def test_post_missing_first_name_returns_400_identity_fields_missing(client):
    body = _mint_body()
    del body["first_name"]
    resp = await client.post("/anchors", json=body)
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "IDENTITY_FIELDS_MISSING"


async def test_post_missing_dob_returns_400_identity_fields_missing(client):
    body = _mint_body()
    del body["date_of_birth"]
    resp = await client.post("/anchors", json=body)
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "IDENTITY_FIELDS_MISSING"


async def test_idempotent_replay_returns_200_with_original_anchor(client):
    crid = _crid()
    first = await client.post("/anchors", json=_mint_body(crid))
    assert first.status_code == 201
    first_body = first.json()

    second = await client.post("/anchors", json=_mint_body(crid))
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["error_code"] == "REQUEST_ALREADY_PROCESSED"
    assert second_body["anchor"]["internal_id"] == first_body["internal_id"]


async def test_get_anchor_after_projection_catches_up_returns_200(client):
    minted = await client.post("/anchors", json=_mint_body())
    assert minted.status_code == 201
    internal_id = minted.json()["internal_id"]

    # Allow the outbox → relay → broker → consumer → projection chain to
    # propagate. The local-loop SLO is well under a second.
    resp = None
    for _ in range(50):
        resp = await client.get(f"/anchors/{internal_id}")
        if resp.status_code == 200:
            break
        await asyncio.sleep(0.1)
    assert resp is not None and resp.status_code == 200, resp.text if resp else "no response"
    body = resp.json()
    assert body["internal_id"] == internal_id
    assert body["anchor_status"] == "ACTIVE"
    assert "ETag" in resp.headers
    assert resp.headers["Cache-Control"] == "max-age=60"


async def test_get_anchor_with_if_none_match_returns_304(client):
    minted = await client.post("/anchors", json=_mint_body())
    internal_id = minted.json()["internal_id"]

    # Wait for projection catch-up.
    etag = None
    for _ in range(50):
        resp = await client.get(f"/anchors/{internal_id}")
        if resp.status_code == 200:
            etag = resp.headers["ETag"]
            break
        await asyncio.sleep(0.1)
    assert etag is not None

    resp2 = await client.get(f"/anchors/{internal_id}", headers={"If-None-Match": etag})
    assert resp2.status_code == 304


async def test_get_anchor_unknown_internal_id_returns_404(client):
    resp = await client.get("/anchors/018f8e10-0000-7000-8000-000000000999")
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "ANCHOR_NOT_FOUND"


async def test_immediate_get_after_post_may_404_before_projection_catchup(client, app_settings):
    """Documents the eventual-consistency contract: a GET issued right after
    a POST may legitimately observe a 404 if the projection has not yet
    caught up. The presentation layer does NOT block on the outbox.

    We assert the weaker invariant: the GET eventually succeeds within a
    bounded window. The 404-first-window observation depends on the
    relay's cycle and may not always trigger; the test only fails if the
    GET fails to converge to 200 at all.
    """
    minted = await client.post("/anchors", json=_mint_body())
    internal_id = minted.json()["internal_id"]
    saw_404 = False
    saw_200 = False
    for _ in range(50):
        resp = await client.get(f"/anchors/{internal_id}")
        if resp.status_code == 404:
            saw_404 = True
        if resp.status_code == 200:
            saw_200 = True
            break
        await asyncio.sleep(0.05)
    # Hard invariant: eventually consistent.
    assert saw_200
    # Soft observation logged for awareness — not enforced.
    if not saw_404:
        # The local loop converges fast enough that the 404 window may not
        # be observable. That's fine — the eventual-consistency contract
        # only requires *eventual* convergence, not an observable lag.
        pass


async def test_outbox_row_is_published_and_status_becomes_PUBLISHED(client, app_settings, pg_dsn):
    """Verify the outbox row transitions from PENDING to PUBLISHED after
    the relay drains it.
    """
    import psycopg

    minted = await client.post("/anchors", json=_mint_body())
    internal_id = minted.json()["internal_id"]

    # Poll the outbox for the PUBLISHED status.
    published = False
    for _ in range(50):
        async with await psycopg.AsyncConnection.connect(pg_dsn) as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT status FROM outbox WHERE correlation_id = %s",
                (internal_id,),
            )
            row = await cur.fetchone()
            if row and row[0] == "PUBLISHED":
                published = True
                break
        await asyncio.sleep(0.1)
    assert published, "outbox row was not marked PUBLISHED within 5s"
