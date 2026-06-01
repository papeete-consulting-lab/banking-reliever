"""Integration tests for the PII-free anchor-history projection (TASK-006).

Covers (against a live Postgres + RabbitMQ via docker compose):

  1. Full-lifecycle history — MINT + UPDATE + PSEUDONYMISE → 3 rows in
     anchor_history (or 5 once ARCHIVE/RESTORE land via TASK-004 — the
     test asserts >= 3 to stay forward-compatible with that landing).
  2. ``GET /anchors/{internal_id}/history`` returns ordered rows by
     ``revision`` ascending and contains the canonical seven fields.
  3. ``?since_revision=N`` filters strictly to ``revision > N``.
  4. ETag + 304 path — second call with ``If-None-Match`` returns 304.
  5. PSEUDONYMISED survives: after pseudonymisation the projection still
     returns the complete sequence; the terminal row bears
     ``right_exercise_id``; PII columns NEVER appear.
  6. Structural PII-free invariant via ``information_schema`` — the
     ``anchor_history`` table has NO ``last_name`` / ``first_name`` /
     ``date_of_birth`` / ``contact_details`` columns.
  7. Retention purge — feed a row with ``occurred_at`` past the cutoff,
     run the job, assert the row is gone; feed one inside the window,
     assert it survives.
  8. At-least-once idempotency — feeding the consumer the SAME RVT
     twice yields ONE history row (composite-PK conflict absorbed).
  9. PII-injection negative — feed a hand-crafted RVT payload with PII
     fields set; assert anchor_history rows contain NO PII columns
     (the projection extracts only the seven contracted fields).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from reliever_beneficiary_anchor.application.handlers import ROUTING_KEY
from reliever_beneficiary_anchor.infrastructure.messaging.projection_consumer import (
    ProjectionConsumer,
)
from reliever_beneficiary_anchor.infrastructure.persistence.history import (
    PostgresAnchorHistoryReader,
    PostgresAnchorHistoryWriter,
    PostgresRetentionPurger,
)
from reliever_beneficiary_anchor.infrastructure.persistence.retention import (
    RetentionPurgeJob,
)
from reliever_beneficiary_anchor.presentation.app import create_app

pytestmark = pytest.mark.integration


# ─── HTTP client fixture (in-process, ASGI) ────────────────────────────


@pytest_asyncio.fixture
async def client(app_settings, reset_db):
    app = create_app(app_settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


def _crid() -> str:
    return f"018f8e10-eeee-7{uuid.uuid4().hex[1:4]}-8{uuid.uuid4().hex[1:4]}-{uuid.uuid4().hex[:12]}"


def _cmd_id() -> str:
    return f"018f8e10-cccc-7{uuid.uuid4().hex[1:4]}-8{uuid.uuid4().hex[1:4]}-{uuid.uuid4().hex[:12]}"


def _mint_body() -> dict:
    return {
        "client_request_id": _crid(),
        "last_name": "Dupont",
        "first_name": "Marie",
        "date_of_birth": "1985-06-21",
        "contact_details": {"email": "marie.dupont@example.org"},
    }


def _update_body() -> dict:
    return {
        "command_id": _cmd_id(),
        "last_name": "Martin",
    }


def _pseudonymise_body() -> dict:
    return {
        "command_id": _cmd_id(),
        "right_exercise_id": f"018f8e10-rrrr-7{uuid.uuid4().hex[1:4]}-8{uuid.uuid4().hex[1:4]}-{uuid.uuid4().hex[:12]}".replace("r", "a"),
        "reason": "GDPR_ART17_REQUEST",
    }


async def _wait_for_history_rows(client: AsyncClient, internal_id: str, n: int, timeout: float = 8.0) -> dict:
    """Poll the history endpoint until ``n`` rows are visible or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    last_body: dict = {}
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/anchors/{internal_id}/history")
        if resp.status_code == 200:
            last_body = resp.json()
            if len(last_body.get("entries", [])) >= n:
                return last_body
        await asyncio.sleep(0.2)
    raise AssertionError(
        f"history did not reach {n} rows in {timeout}s (last body: {last_body})"
    )


# ─── 1. Full-lifecycle history ────────────────────────────────────────


async def test_full_lifecycle_history_minimum_three_rows(client) -> None:
    """MINT → UPDATE → PSEUDONYMISE — 3 rows in the projection.

    Reaches 5 rows once TASK-004 (ARCHIVE/RESTORE) lands; the test stays
    forward-compatible by asserting >= 3.
    """
    mint_resp = await client.post("/anchors", json=_mint_body())
    assert mint_resp.status_code == 201, mint_resp.text
    iid = mint_resp.json()["internal_id"]

    upd = await client.patch(f"/anchors/{iid}", json=_update_body())
    assert upd.status_code == 200, upd.text

    pseudo = await client.post(f"/anchors/{iid}/pseudonymise", json=_pseudonymise_body())
    assert pseudo.status_code == 200, pseudo.text

    body = await _wait_for_history_rows(client, iid, n=3)
    assert body["internal_id"] == iid
    entries = body["entries"]
    assert len(entries) >= 3
    # Strict ascending revision.
    revs = [e["revision"] for e in entries]
    assert revs == sorted(revs)
    # Terminal row is PSEUDONYMISED — and carries the right_exercise_id.
    assert entries[-1]["transition_kind"] == "PSEUDONYMISED"
    assert entries[-1]["right_exercise_id"] is not None


# ─── 2. Canonical seven-field shape ──────────────────────────────────


async def test_history_row_carries_exactly_the_seven_contracted_fields(client) -> None:
    mint_resp = await client.post("/anchors", json=_mint_body())
    iid = mint_resp.json()["internal_id"]
    body = await _wait_for_history_rows(client, iid, n=1)
    entry = body["entries"][0]
    assert set(entry.keys()) == {
        "internal_id",
        "revision",
        "transition_kind",
        "command_id",
        "right_exercise_id",
        "actor",
        "occurred_at",
    }
    # No PII keys leaked from the wire payload.
    for forbidden in ("last_name", "first_name", "date_of_birth", "contact_details"):
        assert forbidden not in entry


# ─── 3. since_revision strict filter ─────────────────────────────────


async def test_since_revision_strict_filter(client) -> None:
    mint_resp = await client.post("/anchors", json=_mint_body())
    iid = mint_resp.json()["internal_id"]
    upd = await client.patch(f"/anchors/{iid}", json=_update_body())
    assert upd.status_code == 200

    body_all = await _wait_for_history_rows(client, iid, n=2)
    full = body_all["entries"]
    assert [e["revision"] for e in full] == sorted(e["revision"] for e in full)

    # Filter to revision > 1 — drop the MINTED row.
    filtered_resp = await client.get(f"/anchors/{iid}/history?since_revision=1")
    assert filtered_resp.status_code == 200
    filtered = filtered_resp.json()["entries"]
    assert all(e["revision"] > 1 for e in filtered)
    assert len(filtered) == len(full) - 1


# ─── 4. ETag + 304 ────────────────────────────────────────────────────


async def test_etag_304_path(client) -> None:
    mint_resp = await client.post("/anchors", json=_mint_body())
    iid = mint_resp.json()["internal_id"]
    body_full = await _wait_for_history_rows(client, iid, n=1)
    # First call — capture ETag.
    first = await client.get(f"/anchors/{iid}/history")
    etag = first.headers.get("etag")
    assert etag is not None
    assert first.headers.get("cache-control") == "max-age=0"

    # Second call with If-None-Match → 304.
    second = await client.get(
        f"/anchors/{iid}/history",
        headers={"If-None-Match": etag},
    )
    assert second.status_code == 304
    assert second.headers.get("etag") == etag


async def test_etag_bumps_after_new_transition(client) -> None:
    mint_resp = await client.post("/anchors", json=_mint_body())
    iid = mint_resp.json()["internal_id"]
    await _wait_for_history_rows(client, iid, n=1)
    first = await client.get(f"/anchors/{iid}/history")
    etag1 = first.headers["etag"]

    upd = await client.patch(f"/anchors/{iid}", json=_update_body())
    assert upd.status_code == 200
    await _wait_for_history_rows(client, iid, n=2)
    second = await client.get(f"/anchors/{iid}/history")
    etag2 = second.headers["etag"]
    assert etag1 != etag2


# ─── 5. PSEUDONYMISED survives ───────────────────────────────────────


async def test_pseudonymised_row_survives_with_right_exercise_id(client) -> None:
    """After PSEUDONYMISE the projection still returns the complete
    sequence; the terminal row bears the right_exercise_id (= GDPR-
    fulfilment proof). No PII column appears anywhere.
    """
    mint_resp = await client.post("/anchors", json=_mint_body())
    iid = mint_resp.json()["internal_id"]
    pseudo = await client.post(f"/anchors/{iid}/pseudonymise", json=_pseudonymise_body())
    assert pseudo.status_code == 200

    body = await _wait_for_history_rows(client, iid, n=2)
    entries = body["entries"]
    assert entries[0]["transition_kind"] == "MINTED"
    assert entries[-1]["transition_kind"] == "PSEUDONYMISED"
    assert entries[-1]["right_exercise_id"] is not None

    # PII-free invariant on every entry.
    for entry in entries:
        for forbidden in ("last_name", "first_name", "date_of_birth", "contact_details"):
            assert forbidden not in entry


# ─── 6. Structural PII-free invariant (information_schema) ───────────


async def test_information_schema_has_no_pii_columns_on_anchor_history(pg_dsn) -> None:
    """The PII-free invariant is structural: the database physically
    cannot store PII in anchor_history.
    """
    async with await psycopg.AsyncConnection.connect(pg_dsn) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'anchor_history'
                """
            )
            cols = {r[0] for r in await cur.fetchall()}
    assert {"internal_id", "revision", "transition_kind", "command_id",
            "right_exercise_id", "actor", "occurred_at"}.issubset(cols)
    for forbidden in ("last_name", "first_name", "date_of_birth", "contact_details"):
        assert forbidden not in cols, (
            f"PII column {forbidden!r} present in anchor_history — "
            f"the projection is PII-free by construction."
        )


# ─── 7. Retention purge ─────────────────────────────────────────────


async def test_retention_purge_removes_old_rows_and_preserves_recent(
    pg_dsn, reset_db
) -> None:
    """Direct test of the purge job: write two rows with controlled
    ``occurred_at`` timestamps, run the job with a 1-day window, and
    assert the old one is gone, the new one survived.
    """
    from psycopg_pool import AsyncConnectionPool

    pool = AsyncConnectionPool(pg_dsn, min_size=1, max_size=2, open=False)
    await pool.open()
    await pool.wait()
    try:
        writer = PostgresAnchorHistoryWriter(pool)
        purger = PostgresRetentionPurger(pool)

        old_iid = "018f8e10-9999-7000-8000-000000000001"
        new_iid = "018f8e10-9999-7000-8000-000000000002"
        old_when = datetime.now(timezone.utc) - timedelta(days=10)
        new_when = datetime.now(timezone.utc) - timedelta(hours=1)

        await writer.append({
            "internal_id": old_iid,
            "revision": 1,
            "transition_kind": "MINTED",
            "command_id": None,
            "right_exercise_id": None,
            "actor": {"kind": "human", "subject": old_iid},
            "occurred_at": old_when,
        })
        await writer.append({
            "internal_id": new_iid,
            "revision": 1,
            "transition_kind": "MINTED",
            "command_id": None,
            "right_exercise_id": None,
            "actor": {"kind": "human", "subject": new_iid},
            "occurred_at": new_when,
        })

        job = RetentionPurgeJob(purger=purger, retention_days=1, interval_seconds=60)
        deleted = await job.run_once()
        assert deleted == 1

        reader = PostgresAnchorHistoryReader(pool)
        assert await reader.list(internal_id=old_iid) == []
        survived = await reader.list(internal_id=new_iid)
        assert len(survived) == 1
    finally:
        await pool.close()


# ─── 8. At-least-once idempotency on the composite PK ───────────────


async def test_duplicate_rvt_delivery_is_idempotent(pg_dsn, reset_db) -> None:
    from psycopg_pool import AsyncConnectionPool

    pool = AsyncConnectionPool(pg_dsn, min_size=1, max_size=2, open=False)
    await pool.open()
    await pool.wait()
    try:
        writer = PostgresAnchorHistoryWriter(pool)
        reader = PostgresAnchorHistoryReader(pool)
        iid = "018f8e10-9999-7000-8000-000000000003"
        row = {
            "internal_id": iid,
            "revision": 1,
            "transition_kind": "MINTED",
            "command_id": "018f8e10-cccc-7000-8000-000000000001",
            "right_exercise_id": None,
            "actor": {"kind": "human", "subject": iid},
            "occurred_at": datetime.now(timezone.utc),
        }
        first = await writer.append(row)
        second = await writer.append(row)
        assert first is True
        assert second is False
        rows = await reader.list(internal_id=iid)
        assert len(rows) == 1
    finally:
        await pool.close()


# ─── 9. PII-injection negative test ─────────────────────────────────


async def test_pii_in_rvt_payload_never_reaches_anchor_history(
    pg_dsn, reset_db
) -> None:
    """Feed the consumer's ``_apply`` method a hand-crafted RVT carrying
    PII in the payload; assert anchor_history NEVER materialises a PII
    column (it has none — and the extraction layer drops anything not
    in the seven-field contract).
    """
    from psycopg_pool import AsyncConnectionPool

    pool = AsyncConnectionPool(pg_dsn, min_size=1, max_size=2, open=False)
    await pool.open()
    await pool.wait()
    try:
        directory_writer = _DirectoryWriterStub()
        history_writer = PostgresAnchorHistoryWriter(pool)
        reader = PostgresAnchorHistoryReader(pool)

        consumer = ProjectionConsumer(
            connection=None,  # type: ignore[arg-type]
            exchange_name="sup.002.ben-events",
            routing_key=ROUTING_KEY,
            queue_name="ignored",
            writer=directory_writer,
            history_writer=history_writer,
            validator=_PassthroughValidator(),
        )

        iid = "018f8e10-9999-7000-8000-000000000004"
        payload = {
            "envelope": {
                "actor": {"kind": "human", "subject": iid},
            },
            "internal_id": iid,
            # PII deliberately present — must never leak into anchor_history.
            "last_name": "Hacker",
            "first_name": "Eve",
            "date_of_birth": "1980-01-01",
            "contact_details": {"email": "eve@example.com"},
            "anchor_status": "ACTIVE",
            "creation_date": "2026-06-01",
            "pseudonymized_at": None,
            "revision": 1,
            "transition_kind": "MINTED",
            "command_id": None,
            "right_exercise_id": None,
            "occurred_at": "2026-06-01T12:00:00+00:00",
        }
        await consumer._apply(payload)

        rows = await reader.list(internal_id=iid)
        assert len(rows) == 1
        # information_schema-level proof (defensive): the row dict from
        # psycopg's dict_row cursor has only the columns the table
        # physically has — by construction PII keys are absent.
        for forbidden in ("last_name", "first_name", "date_of_birth", "contact_details"):
            assert forbidden not in rows[0]
    finally:
        await pool.close()


class _DirectoryWriterStub:
    """Test stub that absorbs directory upserts without touching the DB
    (we only care about the history side in this test).
    """

    async def upsert(self, projection_row: dict) -> bool:  # noqa: ARG002
        return True


class _PassthroughValidator:
    def validate_payload(self, payload: dict) -> None:
        return None
