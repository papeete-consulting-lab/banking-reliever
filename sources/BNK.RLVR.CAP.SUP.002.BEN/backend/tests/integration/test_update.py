"""End-to-end integration test for PATCH /anchors/{internal_id} — runs the
FastAPI app in-process against the docker-compose Postgres + RabbitMQ.

Skips automatically when the infra isn't reachable (see conftest.py).
"""

from __future__ import annotations

import asyncio
import uuid

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from reliever_beneficiary_anchor.presentation.app import create_app

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def client(app_settings, reset_db):
    app = create_app(app_settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


def _crid() -> str:
    return f"018f8e10-eeee-7{uuid.uuid4().hex[1:4]}-8{uuid.uuid4().hex[1:4]}-{uuid.uuid4().hex[:12]}"


def _command_id() -> str:
    return f"018f8e10-cccc-7{uuid.uuid4().hex[1:4]}-8{uuid.uuid4().hex[1:4]}-{uuid.uuid4().hex[:12]}"


def _mint_body(crid: str | None = None) -> dict:
    return {
        "client_request_id": crid or _crid(),
        "last_name": "Dupont",
        "first_name": "Marie",
        "date_of_birth": "1985-06-21",
        "contact_details": {
            "email": "marie.dupont@example.org",
            "phone": "+33 1 23 45 67 89",
        },
    }


async def _mint(client: AsyncClient) -> str:
    resp = await client.post("/anchors", json=_mint_body())
    assert resp.status_code == 201, resp.text
    return resp.json()["internal_id"]


async def _wait_for_projection(client: AsyncClient, internal_id: str, expected_revision: int) -> dict:
    """Poll the GET endpoint until the projection has caught up to
    ``expected_revision``. Returns the body of the successful GET.
    """
    for _ in range(60):
        resp = await client.get(f"/anchors/{internal_id}")
        if resp.status_code == 200 and resp.json().get("revision") == expected_revision:
            return resp.json()
        await asyncio.sleep(0.1)
    raise AssertionError(
        f"Projection did not catch up to revision={expected_revision} for "
        f"internal_id={internal_id} within 6s"
    )


# ─── Happy path ────────────────────────────────────────────────────────


async def test_patch_returns_200_with_bumped_revision(client):
    internal_id = await _mint(client)
    body = {
        "command_id": _command_id(),
        "first_name": "Maryam",
    }
    resp = await client.patch(f"/anchors/{internal_id}", json=body)
    assert resp.status_code == 200, resp.text
    anchor = resp.json()
    assert anchor["revision"] == 2
    assert anchor["first_name"] == "Maryam"
    assert anchor["last_name"] == "Dupont"  # sticky


async def test_patch_then_get_reflects_update_and_etag_changes(client):
    internal_id = await _mint(client)
    # Wait for the projection of the MINT.
    initial = await _wait_for_projection(client, internal_id, expected_revision=1)
    initial_get = await client.get(f"/anchors/{internal_id}")
    initial_etag = initial_get.headers["ETag"]

    # Apply the update.
    patch_resp = await client.patch(
        f"/anchors/{internal_id}",
        json={"command_id": _command_id(), "first_name": "Maryam"},
    )
    assert patch_resp.status_code == 200

    # The PATCH response itself carries an ETag bumped to revision 2 already.
    patch_etag = patch_resp.headers["ETag"]
    assert patch_etag != initial_etag

    # GET converges to revision 2.
    final = await _wait_for_projection(client, internal_id, expected_revision=2)
    assert final["first_name"] == "Maryam"
    final_get = await client.get(f"/anchors/{internal_id}")
    final_etag = final_get.headers["ETag"]
    assert final_etag != initial_etag


# ─── Sticky-PII (INV.BEN.003) ──────────────────────────────────────────


async def test_absent_field_is_no_op_at_get(client):
    internal_id = await _mint(client)
    await _wait_for_projection(client, internal_id, expected_revision=1)
    await client.patch(
        f"/anchors/{internal_id}",
        json={"command_id": _command_id(), "first_name": "Maryam"},
    )
    body = await _wait_for_projection(client, internal_id, expected_revision=2)
    # last_name / contact_details preserved.
    assert body["last_name"] == "Dupont"
    assert body["contact_details"]["email"] == "marie.dupont@example.org"
    assert body["contact_details"]["phone"] == "+33 1 23 45 67 89"


async def test_explicit_null_on_email_clears_only_email(client):
    internal_id = await _mint(client)
    await _wait_for_projection(client, internal_id, expected_revision=1)
    resp = await client.patch(
        f"/anchors/{internal_id}",
        json={
            "command_id": _command_id(),
            "contact_details": {"email": None},
        },
    )
    assert resp.status_code == 200, resp.text
    body = await _wait_for_projection(client, internal_id, expected_revision=2)
    assert body["contact_details"]["email"] is None
    assert body["contact_details"]["phone"] == "+33 1 23 45 67 89"  # sticky


# ─── Idempotency (INV.BEN.008) ─────────────────────────────────────────


async def test_idempotent_replay_returns_200_with_command_already_processed(client):
    internal_id = await _mint(client)
    cid = _command_id()
    first = await client.patch(
        f"/anchors/{internal_id}",
        json={"command_id": cid, "first_name": "Maryam"},
    )
    assert first.status_code == 200
    first_body = first.json()

    second = await client.patch(
        f"/anchors/{internal_id}",
        json={"command_id": cid, "first_name": "Maryam"},
    )
    assert second.status_code == 200
    payload = second.json()
    assert payload["error_code"] == "COMMAND_ALREADY_PROCESSED"
    assert payload["anchor"]["internal_id"] == first_body["internal_id"]
    assert payload["anchor"]["revision"] == first_body["revision"]


async def test_idempotent_replay_does_not_write_second_outbox_row(client, pg_dsn):
    internal_id = await _mint(client)
    cid = _command_id()
    await client.patch(
        f"/anchors/{internal_id}",
        json={"command_id": cid, "first_name": "Maryam"},
    )
    await client.patch(
        f"/anchors/{internal_id}",
        json={"command_id": cid, "first_name": "Maryam"},
    )
    # Look at outbox: there must be exactly one row whose payload carries
    # transition_kind=UPDATED for this anchor.
    async with await psycopg.AsyncConnection.connect(pg_dsn) as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT COUNT(*)
            FROM outbox
            WHERE correlation_id = %s
              AND payload->>'transition_kind' = 'UPDATED'
            """,
            (internal_id,),
        )
        row = await cur.fetchone()
    assert row is not None and row[0] == 1


# ─── Error paths ───────────────────────────────────────────────────────


async def test_patch_unknown_anchor_returns_404(client):
    resp = await client.patch(
        "/anchors/018f8e10-0000-7000-8000-000000000999",
        json={"command_id": _command_id(), "first_name": "Maryam"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "ANCHOR_NOT_FOUND"


async def test_patch_with_internal_id_in_body_returns_400(client):
    internal_id = await _mint(client)
    resp = await client.patch(
        f"/anchors/{internal_id}",
        json={
            "command_id": _command_id(),
            "internal_id": internal_id,  # ← INV.BEN.002 violation
            "first_name": "Maryam",
        },
    )
    # Schema-level rejection (additionalProperties: false) precedes the
    # explicit guard, both yield 400.
    assert resp.status_code == 400


async def test_patch_with_only_command_id_returns_400_no_fields_to_update(client):
    internal_id = await _mint(client)
    resp = await client.patch(
        f"/anchors/{internal_id}",
        json={"command_id": _command_id()},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "NO_FIELDS_TO_UPDATE"


# ─── Lifecycle guards — manually flip status to ARCHIVED / PSEUDONYMISED ──
#
# Since TASK-004 / TASK-005 do not yet exist, we exercise the 409 paths by
# patching the write-side anchor row directly via psycopg, then issuing a
# PATCH. This is integration-level only and only used to assert the
# lifecycle-guard behaviour of UPDATE.


async def test_patch_archived_anchor_returns_409_anchor_archived(client, pg_dsn):
    internal_id = await _mint(client)
    async with await psycopg.AsyncConnection.connect(pg_dsn) as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE anchor SET anchor_status='ARCHIVED' WHERE internal_id=%s",
            (internal_id,),
        )
        await conn.commit()
    resp = await client.patch(
        f"/anchors/{internal_id}",
        json={"command_id": _command_id(), "first_name": "Maryam"},
    )
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "ANCHOR_ARCHIVED"


async def test_patch_pseudonymised_anchor_returns_409_anchor_pseudonymised(
    client, pg_dsn,
):
    internal_id = await _mint(client)
    async with await psycopg.AsyncConnection.connect(pg_dsn) as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE anchor SET anchor_status='PSEUDONYMISED' WHERE internal_id=%s",
            (internal_id,),
        )
        await conn.commit()
    resp = await client.patch(
        f"/anchors/{internal_id}",
        json={"command_id": _command_id(), "first_name": "Maryam"},
    )
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "ANCHOR_PSEUDONYMISED"


# ─── Outbox is published exactly once ──────────────────────────────────


async def test_update_outbox_row_is_published(client, pg_dsn):
    internal_id = await _mint(client)
    await client.patch(
        f"/anchors/{internal_id}",
        json={"command_id": _command_id(), "first_name": "Maryam"},
    )
    # Poll for the UPDATED outbox row to transition to PUBLISHED.
    published = False
    for _ in range(60):
        async with await psycopg.AsyncConnection.connect(pg_dsn) as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT status FROM outbox
                WHERE correlation_id = %s
                  AND payload->>'transition_kind' = 'UPDATED'
                """,
                (internal_id,),
            )
            row = await cur.fetchone()
            if row and row[0] == "PUBLISHED":
                published = True
                break
        await asyncio.sleep(0.1)
    assert published, "UPDATED outbox row was not marked PUBLISHED within 6s"
