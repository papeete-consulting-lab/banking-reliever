"""End-to-end integration test for the lifecycle verbs (TASK-004):

    POST /anchors/{internal_id}/archive   — CMD.ARCHIVE_ANCHOR
    POST /anchors/{internal_id}/restore   — CMD.RESTORE_ANCHOR

Runs the FastAPI app in-process against the docker-compose Postgres +
RabbitMQ. Skips automatically when the infra isn't reachable (conftest.py).
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
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


def _uuidv7() -> str:
    return f"018f8e10-cccc-7{uuid.uuid4().hex[1:4]}-8{uuid.uuid4().hex[1:4]}-{uuid.uuid4().hex[:12]}"


def _mint_body() -> dict:
    return {
        "client_request_id": _uuidv7(),
        "last_name": "Dupont",
        "first_name": "Marie",
        "date_of_birth": "1985-06-21",
        "contact_details": {"email": "marie.dupont@example.org", "phone": "+33 1 23 45 67 89"},
    }


async def _mint(client: AsyncClient) -> str:
    resp = await client.post("/anchors", json=_mint_body())
    assert resp.status_code == 201, resp.text
    return resp.json()["internal_id"]


async def _wait_for_projection(client: AsyncClient, internal_id: str, expected_revision: int) -> dict:
    for _ in range(60):
        resp = await client.get(f"/anchors/{internal_id}")
        if resp.status_code == 200 and resp.json().get("revision") == expected_revision:
            return resp.json()
        await asyncio.sleep(0.1)
    raise AssertionError(
        f"Projection did not reach revision={expected_revision} for {internal_id} within 6s"
    )


# ─── Happy path ────────────────────────────────────────────────────────


async def test_archive_flips_status_and_bumps_revision(client):
    internal_id = await _mint(client)
    resp = await client.post(
        f"/anchors/{internal_id}/archive",
        json={"command_id": _uuidv7(), "reason": "PROGRAMME_EXIT_SUCCESS"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["anchor_status"] == "ARCHIVED"
    assert body["revision"] == 2
    assert body["last_name"] == "Dupont"  # PII unchanged


async def test_get_resolves_archived_anchor(client):
    internal_id = await _mint(client)
    await client.post(
        f"/anchors/{internal_id}/archive",
        json={"command_id": _uuidv7(), "reason": "ADMINISTRATIVE_ARCHIVAL"},
    )
    body = await _wait_for_projection(client, internal_id, expected_revision=2)
    assert body["anchor_status"] == "ARCHIVED"
    # Referential read is not gated on status (INV.BEN.004).
    get_resp = await client.get(f"/anchors/{internal_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["anchor_status"] == "ARCHIVED"


async def test_archive_then_restore_round_trip(client):
    internal_id = await _mint(client)
    arch = await client.post(
        f"/anchors/{internal_id}/archive",
        json={"command_id": _uuidv7(), "reason": "PROGRAMME_EXIT_DROPOUT"},
    )
    assert arch.status_code == 200
    arch_etag = arch.headers["ETag"]

    rest = await client.post(
        f"/anchors/{internal_id}/restore",
        json={"command_id": _uuidv7(), "reason": "ARCHIVED_IN_ERROR"},
    )
    assert rest.status_code == 200, rest.text
    body = rest.json()
    assert body["anchor_status"] == "ACTIVE"
    assert body["revision"] == 3
    # ETag flips on every transition.
    assert rest.headers["ETag"] != arch_etag

    final = await _wait_for_projection(client, internal_id, expected_revision=3)
    assert final["anchor_status"] == "ACTIVE"
    assert final["last_name"] == "Dupont"  # PII continuity


# ─── State-machine guards ──────────────────────────────────────────────


async def test_double_archive_returns_409_already_archived(client):
    internal_id = await _mint(client)
    await client.post(
        f"/anchors/{internal_id}/archive",
        json={"command_id": _uuidv7(), "reason": "PROGRAMME_EXIT_SUCCESS"},
    )
    second = await client.post(
        f"/anchors/{internal_id}/archive",
        json={"command_id": _uuidv7(), "reason": "PROGRAMME_EXIT_SUCCESS"},
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "ANCHOR_ALREADY_ARCHIVED"


async def test_restore_active_returns_409_not_archived(client):
    internal_id = await _mint(client)
    resp = await client.post(
        f"/anchors/{internal_id}/restore",
        json={"command_id": _uuidv7(), "reason": "ARCHIVED_IN_ERROR"},
    )
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "ANCHOR_NOT_ARCHIVED"


async def test_archive_unknown_returns_404(client):
    resp = await client.post(
        f"/anchors/{_uuidv7()}/archive",
        json={"command_id": _uuidv7(), "reason": "PROGRAMME_EXIT_SUCCESS"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "ANCHOR_NOT_FOUND"


async def test_restore_unknown_returns_404(client):
    resp = await client.post(
        f"/anchors/{_uuidv7()}/restore",
        json={"command_id": _uuidv7(), "reason": "ARCHIVED_IN_ERROR"},
    )
    assert resp.status_code == 404


# ─── Reason enum validation ────────────────────────────────────────────


async def test_archive_missing_reason_returns_400(client):
    internal_id = await _mint(client)
    resp = await client.post(
        f"/anchors/{internal_id}/archive",
        json={"command_id": _uuidv7()},
    )
    assert resp.status_code == 400


async def test_archive_invalid_reason_returns_400(client):
    internal_id = await _mint(client)
    resp = await client.post(
        f"/anchors/{internal_id}/archive",
        json={"command_id": _uuidv7(), "reason": "NOT_A_REAL_REASON"},
    )
    assert resp.status_code == 400


# ─── Idempotency (INV.BEN.008) ─────────────────────────────────────────


async def test_archive_idempotent_replay(client):
    internal_id = await _mint(client)
    cid = _uuidv7()
    first = await client.post(
        f"/anchors/{internal_id}/archive",
        json={"command_id": cid, "reason": "PROGRAMME_EXIT_SUCCESS"},
    )
    assert first.status_code == 200
    assert first.json()["anchor_status"] == "ARCHIVED"

    second = await client.post(
        f"/anchors/{internal_id}/archive",
        json={"command_id": cid, "reason": "PROGRAMME_EXIT_SUCCESS"},
    )
    assert second.status_code == 200
    body = second.json()
    assert body["error_code"] == "COMMAND_ALREADY_PROCESSED"
    assert body["anchor"]["revision"] == 2  # no second transition


# ─── Cross-verb guard (TASK-003 UPDATE on an ARCHIVED anchor) ──────────


async def test_update_on_archived_anchor_returns_409_archived(client):
    internal_id = await _mint(client)
    await client.post(
        f"/anchors/{internal_id}/archive",
        json={"command_id": _uuidv7(), "reason": "PROGRAMME_EXIT_SUCCESS"},
    )
    resp = await client.patch(
        f"/anchors/{internal_id}",
        json={"command_id": _uuidv7(), "first_name": "Maryam"},
    )
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "ANCHOR_ARCHIVED"
