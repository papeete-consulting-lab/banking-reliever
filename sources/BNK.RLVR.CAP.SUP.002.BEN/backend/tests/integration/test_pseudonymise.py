"""End-to-end integration test for POST /anchors/{internal_id}/pseudonymise
— TASK-005.

Runs the FastAPI app in-process against the docker-compose Postgres +
RabbitMQ. Skips automatically when the infra isn't reachable (see
conftest.py).

Covers Definition of Done:

  * ACTIVE → PSEUDONYMISED happy path (DoD #1, #5, #6, #7).
  * ARCHIVED → PSEUDONYMISED happy path (DoD: INV.BEN.006).
  * 404 on unknown anchor (DoD #3).
  * 409 ANCHOR_ALREADY_PSEUDONYMISED on second-attempt (DoD #2).
  * 400 RIGHT_EXERCISE_ID_INVALID on missing / malformed UUIDv7 (DoD #4).
  * Crypto-shred observable post-condition: a direct SQL inspection of
    the anchor row + the anchor_crypto_keys table confirms PII columns are
    NULL and the per-anchor DEK row is gone (DoD #5).
  * internal_id is unchanged (DoD: INV.BEN.002).
  * Idempotency on command_id: 200 + COMMAND_ALREADY_PROCESSED, no second
    outbox row, no second DEK shred (DoD #9, #11).
  * Outbox: exactly one RVT per successful pseudonymise; payload's PII
    fields null, right_exercise_id set, pseudonymized_at set,
    transition_kind=PSEUDONYMISED, revision=N+1 (DoD #11, #12).
  * Projection: PRJ.ANCHOR_DIRECTORY overwrites with PII NULL (DoD #13).
  * GET returns the row with PII fields null and anchor_status
    PSEUDONYMISED, ETag flipped (DoD #14).
  * UPDATE against a PSEUDONYMISED anchor returns 409 ANCHOR_PSEUDONYMISED
    (DoD #15 — cross-verb regression test against TASK-003).
"""

from __future__ import annotations

import asyncio
import uuid

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from uuid_extensions import uuid7

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
    return str(uuid7())


def _mint_body(crid: str | None = None) -> dict:
    return {
        "client_request_id": crid or _uuidv7(),
        "last_name": "Dupont",
        "first_name": "Marie",
        "date_of_birth": "1985-06-21",
        "contact_details": {
            "email": "marie.dupont@example.org",
            "phone": "+33 1 23 45 67 89",
        },
    }


def _pseudonymise_body(
    *,
    command_id: str | None = None,
    right_exercise_id: str | None = None,
    reason: str = "GDPR_ART17_REQUEST",
) -> dict:
    return {
        "command_id": command_id or _uuidv7(),
        "right_exercise_id": right_exercise_id or _uuidv7(),
        "reason": reason,
    }


async def _mint(client: AsyncClient) -> str:
    resp = await client.post("/anchors", json=_mint_body())
    assert resp.status_code == 201, resp.text
    return resp.json()["internal_id"]


async def _wait_for_projection(
    client: AsyncClient, internal_id: str, expected_revision: int,
) -> dict:
    for _ in range(60):
        resp = await client.get(f"/anchors/{internal_id}")
        if resp.status_code == 200 and resp.json().get("revision") == expected_revision:
            return resp.json()
        await asyncio.sleep(0.1)
    raise AssertionError(
        f"Projection did not catch up to revision={expected_revision} for "
        f"internal_id={internal_id} within 6s"
    )


# ─── DoD #1 + #5 + #6 + #7 — ACTIVE → PSEUDONYMISED happy path ─────────


async def test_pseudonymise_returns_200_with_pii_null_and_status_pseudonymised(
    client,
):
    internal_id = await _mint(client)
    right_id = _uuidv7()
    body = _pseudonymise_body(right_exercise_id=right_id)

    resp = await client.post(
        f"/anchors/{internal_id}/pseudonymise", json=body,
    )
    assert resp.status_code == 200, resp.text
    anchor = resp.json()
    assert anchor["anchor_status"] == "PSEUDONYMISED"
    assert anchor["last_name"] is None
    assert anchor["first_name"] is None
    assert anchor["date_of_birth"] is None
    assert anchor["contact_details"] is None
    assert anchor["internal_id"] == internal_id  # INV.BEN.002 preserved
    assert anchor["pseudonymized_at"] is not None
    assert anchor["revision"] == 2  # N+1


# ─── DoD: INV.BEN.006 — ARCHIVED → PSEUDONYMISED ───────────────────────


async def test_pseudonymise_archived_anchor_succeeds(client, pg_dsn):
    """INV.BEN.006 — ARCHIVED is a valid source state for PSEUDONYMISE.

    TASK-004 (ARCHIVE) is not in this main yet, so we manually flip the
    write-side row to ARCHIVED via SQL, mirroring the test_update.py
    pattern.
    """
    internal_id = await _mint(client)
    async with await psycopg.AsyncConnection.connect(pg_dsn) as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE anchor SET anchor_status='ARCHIVED' WHERE internal_id=%s",
            (internal_id,),
        )
        await conn.commit()

    resp = await client.post(
        f"/anchors/{internal_id}/pseudonymise",
        json=_pseudonymise_body(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["anchor_status"] == "PSEUDONYMISED"


# ─── DoD #5 — Crypto-shredding observable post-condition ───────────────


async def test_db_inspection_confirms_pii_columns_are_null_and_dek_is_destroyed(
    client, pg_dsn,
):
    """DBA-style audit query — confirms the four PII columns are NULL on
    the anchor row AND the per-anchor DEK row has been destroyed.
    """
    internal_id = await _mint(client)
    # Capture the DEK id before shredding so we can audit it afterwards.
    async with await psycopg.AsyncConnection.connect(pg_dsn) as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT crypto_key_id FROM anchor WHERE internal_id=%s",
            (internal_id,),
        )
        row = await cur.fetchone()
        assert row is not None and row[0] is not None
        original_key_id = str(row[0])

    resp = await client.post(
        f"/anchors/{internal_id}/pseudonymise",
        json=_pseudonymise_body(),
    )
    assert resp.status_code == 200

    # DBA-style audit query — runs OUTSIDE the service.
    async with await psycopg.AsyncConnection.connect(pg_dsn) as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT last_name, first_name, date_of_birth, contact_details,
                   anchor_status, crypto_key_id, pseudonymized_at
            FROM anchor
            WHERE internal_id = %s
            """,
            (internal_id,),
        )
        row = await cur.fetchone()
    assert row is not None
    last_name, first_name, dob, contact_details, status, ckid, pseudo_at = row
    assert last_name is None
    assert first_name is None
    assert dob is None
    assert contact_details is None
    assert status == "PSEUDONYMISED"
    assert ckid is None  # FK severed
    assert pseudo_at is not None

    # The DEK row itself is gone.
    async with await psycopg.AsyncConnection.connect(pg_dsn) as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM anchor_crypto_keys WHERE crypto_key_id = %s",
            (original_key_id,),
        )
        row = await cur.fetchone()
    assert row is not None and row[0] == 0, (
        f"DEK row {original_key_id} should be gone — at-rest ciphertext is unrecoverable"
    )


async def test_db_check_constraint_blocks_pseudonymised_with_non_null_pii(
    client, pg_dsn,
):
    """Defence-in-depth: the CHECK constraint on the anchor table makes
    the (PSEUDONYMISED + non-null PII) state unforgeable at the database
    layer."""
    internal_id = await _mint(client)
    # Try to set status to PSEUDONYMISED without nulling PII — the
    # constraint must reject the UPDATE.
    async with await psycopg.AsyncConnection.connect(pg_dsn) as conn, conn.cursor() as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            await cur.execute(
                """
                UPDATE anchor
                SET anchor_status='PSEUDONYMISED', pseudonymized_at=NOW()
                WHERE internal_id=%s
                """,
                (internal_id,),
            )


# ─── DoD #2 — Terminal state guard (409) ───────────────────────────────


async def test_second_pseudonymise_returns_409_anchor_already_pseudonymised(
    client,
):
    internal_id = await _mint(client)
    first = await client.post(
        f"/anchors/{internal_id}/pseudonymise",
        json=_pseudonymise_body(),
    )
    assert first.status_code == 200

    # Different command_id so we don't trip the idempotency path; the
    # 409 must come from the terminal-state guard.
    second = await client.post(
        f"/anchors/{internal_id}/pseudonymise",
        json=_pseudonymise_body(command_id=_uuidv7()),
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "ANCHOR_ALREADY_PSEUDONYMISED"


# ─── DoD #3 — Unknown anchor (404) ─────────────────────────────────────


async def test_pseudonymise_unknown_anchor_returns_404(client):
    resp = await client.post(
        "/anchors/018f8e10-0000-7000-8000-000000000999/pseudonymise",
        json=_pseudonymise_body(),
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "ANCHOR_NOT_FOUND"


# ─── DoD #4 — Right exercise id invalid (400) ──────────────────────────


async def test_pseudonymise_missing_right_exercise_id_returns_400(client):
    internal_id = await _mint(client)
    body = {
        "command_id": _uuidv7(),
        "reason": "GDPR_ART17_REQUEST",
    }
    resp = await client.post(
        f"/anchors/{internal_id}/pseudonymise", json=body,
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "RIGHT_EXERCISE_ID_INVALID"


async def test_pseudonymise_non_uuidv7_right_exercise_id_returns_400(client):
    internal_id = await _mint(client)
    body = {
        "command_id": _uuidv7(),
        "right_exercise_id": "not-a-uuid",
        "reason": "GDPR_ART17_REQUEST",
    }
    resp = await client.post(
        f"/anchors/{internal_id}/pseudonymise", json=body,
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "RIGHT_EXERCISE_ID_INVALID"


async def test_pseudonymise_uuidv4_right_exercise_id_returns_400(client):
    """UUIDv4 has the wrong version nibble — schema pattern rejects."""
    internal_id = await _mint(client)
    body = {
        "command_id": _uuidv7(),
        "right_exercise_id": str(uuid.uuid4()),  # v4, not v7
        "reason": "GDPR_ART17_REQUEST",
    }
    resp = await client.post(
        f"/anchors/{internal_id}/pseudonymise", json=body,
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "RIGHT_EXERCISE_ID_INVALID"


# ─── DoD #9 + #11 — Idempotency on command_id ──────────────────────────


async def test_idempotent_replay_returns_200_with_command_already_processed(
    client,
):
    internal_id = await _mint(client)
    cid = _uuidv7()
    body = _pseudonymise_body(command_id=cid)
    first = await client.post(
        f"/anchors/{internal_id}/pseudonymise", json=body,
    )
    assert first.status_code == 200

    second = await client.post(
        f"/anchors/{internal_id}/pseudonymise", json=body,
    )
    assert second.status_code == 200
    payload = second.json()
    assert payload["error_code"] == "COMMAND_ALREADY_PROCESSED"
    assert payload["anchor"]["internal_id"] == internal_id
    assert payload["anchor"]["anchor_status"] == "PSEUDONYMISED"


async def test_idempotent_replay_does_not_write_second_outbox_row(
    client, pg_dsn,
):
    internal_id = await _mint(client)
    cid = _uuidv7()
    body = _pseudonymise_body(command_id=cid)
    await client.post(f"/anchors/{internal_id}/pseudonymise", json=body)
    await client.post(f"/anchors/{internal_id}/pseudonymise", json=body)

    async with await psycopg.AsyncConnection.connect(pg_dsn) as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT COUNT(*)
            FROM outbox
            WHERE correlation_id = %s
              AND payload->>'transition_kind' = 'PSEUDONYMISED'
            """,
            (internal_id,),
        )
        row = await cur.fetchone()
    assert row is not None and row[0] == 1


# ─── DoD #11 + #12 — Outbox row + schema validation ────────────────────


async def test_outbox_carries_pseudonymised_branch_payload(client, pg_dsn):
    internal_id = await _mint(client)
    right_id = _uuidv7()
    body = _pseudonymise_body(right_exercise_id=right_id)
    await client.post(f"/anchors/{internal_id}/pseudonymise", json=body)

    async with await psycopg.AsyncConnection.connect(pg_dsn) as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT payload
            FROM outbox
            WHERE correlation_id = %s
              AND payload->>'transition_kind' = 'PSEUDONYMISED'
            """,
            (internal_id,),
        )
        row = await cur.fetchone()
    assert row is not None
    payload = row[0]
    assert payload["transition_kind"] == "PSEUDONYMISED"
    assert payload["anchor_status"] == "PSEUDONYMISED"
    assert payload["last_name"] is None
    assert payload["first_name"] is None
    assert payload["date_of_birth"] is None
    assert payload["contact_details"] is None
    assert payload["right_exercise_id"] == right_id
    assert payload["pseudonymized_at"] is not None
    assert payload["revision"] == 2


async def test_outbox_row_is_published(client, pg_dsn):
    internal_id = await _mint(client)
    body = _pseudonymise_body()
    await client.post(f"/anchors/{internal_id}/pseudonymise", json=body)

    published = False
    for _ in range(60):
        async with await psycopg.AsyncConnection.connect(pg_dsn) as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT status FROM outbox
                WHERE correlation_id = %s
                  AND payload->>'transition_kind' = 'PSEUDONYMISED'
                """,
                (internal_id,),
            )
            row = await cur.fetchone()
            if row and row[0] == "PUBLISHED":
                published = True
                break
        await asyncio.sleep(0.1)
    assert published, "PSEUDONYMISED outbox row was not PUBLISHED within 6s"


# ─── DoD #13 — Projection ingests with PII nulled ──────────────────────


async def test_projection_overwrites_pii_with_null(client):
    internal_id = await _mint(client)
    # Wait for the MINT projection.
    await _wait_for_projection(client, internal_id, expected_revision=1)

    resp = await client.post(
        f"/anchors/{internal_id}/pseudonymise",
        json=_pseudonymise_body(),
    )
    assert resp.status_code == 200

    # Projection converges to revision 2 with PII null.
    body = await _wait_for_projection(client, internal_id, expected_revision=2)
    assert body["anchor_status"] == "PSEUDONYMISED"
    assert body["last_name"] is None
    assert body["first_name"] is None
    assert body["date_of_birth"] is None
    assert body["contact_details"] is None
    assert body["internal_id"] == internal_id


# ─── DoD #14 — GET returns null PII, ETag flips ────────────────────────


async def test_get_after_pseudonymise_returns_pii_null_and_etag_flips(
    client,
):
    internal_id = await _mint(client)
    await _wait_for_projection(client, internal_id, expected_revision=1)
    initial_get = await client.get(f"/anchors/{internal_id}")
    initial_etag = initial_get.headers["ETag"]

    post_resp = await client.post(
        f"/anchors/{internal_id}/pseudonymise",
        json=_pseudonymise_body(),
    )
    assert post_resp.status_code == 200
    post_etag = post_resp.headers["ETag"]
    assert post_etag != initial_etag

    await _wait_for_projection(client, internal_id, expected_revision=2)
    final_get = await client.get(f"/anchors/{internal_id}")
    final_body = final_get.json()
    assert final_body["last_name"] is None
    assert final_body["anchor_status"] == "PSEUDONYMISED"
    assert final_body["internal_id"] == internal_id  # historical references unbroken
    final_etag = final_get.headers["ETag"]
    assert final_etag != initial_etag


# ─── DoD #15 — Cross-verb regression (UPDATE against PSEUDONYMISED) ────


async def test_update_on_pseudonymised_anchor_returns_409_anchor_pseudonymised(
    client,
):
    internal_id = await _mint(client)
    await client.post(
        f"/anchors/{internal_id}/pseudonymise",
        json=_pseudonymise_body(),
    )

    resp = await client.patch(
        f"/anchors/{internal_id}",
        json={"command_id": _uuidv7(), "first_name": "Maryam"},
    )
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "ANCHOR_PSEUDONYMISED"
