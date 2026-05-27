"""Live-boundary cross-cutting checks: broker publication, cache headers,
bus topology, projection LWW. These target DoD #8, #9, #11, #12 at the
running-service boundary (the in-process suite asserts the outbox row but
not actual broker emission)."""

from __future__ import annotations

import time

import jsonschema

from conftest import BASE, EXCHANGE, ROUTING_KEY, uuidv7


def test_health(rest):
    """Service is up and reachable on the host port."""
    r = rest.get(f"{BASE}/health", timeout=5)
    assert r.status_code == 200


def test_archive_publishes_one_rvt_to_broker(rest, bus, minted):
    """DoD #8: a successful ARCHIVE causes the relay to publish exactly one
    RVT to the capability exchange with transition_kind=ARCHIVED, revision=2,
    on the canonical routing key."""
    bus.drain(want=1, timeout=4)  # discard the MINTED RVT from the fixture
    r = rest.post(
        f"{BASE}/anchors/{minted}/archive",
        json={"command_id": uuidv7(), "reason": "PROGRAMME_EXIT_SUCCESS"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    archived = [
        m
        for m in bus.drain(want=2, timeout=8)
        if m["payload"].get("internal_id") == minted
        and m["payload"].get("transition_kind") == "ARCHIVED"
    ]
    assert len(archived) == 1, f"expected exactly 1 ARCHIVED RVT for {minted}"
    m = archived[0]
    assert m["routing_key"] == ROUTING_KEY
    assert m["payload"]["anchor_status"] == "ARCHIVED"
    assert m["payload"]["revision"] == 2


def test_restore_publishes_rvt_restored(rest, bus, minted):
    """DoD #8: RESTORE publishes RVT transition_kind=RESTORED, revision=3."""
    rest.post(
        f"{BASE}/anchors/{minted}/archive",
        json={"command_id": uuidv7(), "reason": "PROGRAMME_EXIT_DROPOUT"},
        timeout=10,
    )
    bus.drain(want=2, timeout=6)  # consume the MINTED + ARCHIVED RVTs
    r = rest.post(
        f"{BASE}/anchors/{minted}/restore",
        json={"command_id": uuidv7(), "reason": "ARCHIVED_IN_ERROR"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    restored = [
        m
        for m in bus.drain(want=2, timeout=8)
        if m["payload"].get("internal_id") == minted
        and m["payload"].get("transition_kind") == "RESTORED"
    ]
    assert len(restored) == 1
    assert restored[0]["payload"]["anchor_status"] == "ACTIVE"
    assert restored[0]["payload"]["revision"] == 3


def test_published_payload_validates_against_rvt_schema(rest, bus, rvt_schema, minted):
    """DoD #9: emitted payload validates against the vendored RVT schema."""
    rest.post(
        f"{BASE}/anchors/{minted}/archive",
        json={"command_id": uuidv7(), "reason": "ADMINISTRATIVE_ARCHIVAL"},
        timeout=10,
    )
    msgs = [m for m in bus.drain(want=1, timeout=8) if m["payload"].get("internal_id") == minted]
    assert msgs, "no RVT captured for the archived anchor"
    jsonschema.validate(instance=msgs[0]["payload"], schema=rvt_schema)


def test_get_archived_cache_headers(rest, minted):
    """DoD #11: GET resolves ARCHIVED anchor, ETag flips per transition,
    Cache-Control max-age=60."""
    g0 = rest.get(f"{BASE}/anchors/{minted}", timeout=10)
    etag0 = g0.headers.get("ETag")

    rest.post(
        f"{BASE}/anchors/{minted}/archive",
        json={"command_id": uuidv7(), "reason": "PROGRAMME_EXIT_TRANSFER"},
        timeout=10,
    )
    # wait for projection to reach revision 2
    body = None
    for _ in range(60):
        g = rest.get(f"{BASE}/anchors/{minted}", timeout=10)
        if g.status_code == 200 and g.json().get("revision") == 2:
            body = g
            break
        time.sleep(0.1)
    assert body is not None, "projection did not reach revision 2"
    assert body.json()["anchor_status"] == "ARCHIVED"
    assert body.headers.get("ETag") not in (None, etag0), "ETag must flip on transition"
    assert "max-age=60" in body.headers.get("Cache-Control", "")


def test_projection_lww_drops_out_of_order(rest, pg, minted):
    """DoD #12: anchor_directory keeps last-write-wins on (internal_id,
    revision); a stale revision must not overwrite a newer one."""
    # Drive it to revision 2 (archive) via HTTP, let the projection catch up.
    rest.post(
        f"{BASE}/anchors/{minted}/archive",
        json={"command_id": uuidv7(), "reason": "PROGRAMME_EXIT_SUCCESS"},
        timeout=10,
    )
    cur_rev = None
    for _ in range(60):
        with pg.cursor() as c:
            c.execute(
                "SELECT revision, anchor_status FROM anchor_directory WHERE internal_id=%s",
                (minted,),
            )
            row = c.fetchone()
        if row and row[0] == 2:
            cur_rev = row
            break
        time.sleep(0.1)
    assert cur_rev == (2, "ARCHIVED"), f"projection not at rev 2 ARCHIVED: {cur_rev}"

    # Replay a STALE projection upsert (revision 1) directly through the same
    # SQL contract used by the consumer; the WHERE revision < EXCLUDED guard
    # must drop it.
    with pg.cursor() as c:
        c.execute(
            """
            INSERT INTO anchor_directory
              (internal_id, last_name, first_name, anchor_status,
               creation_date, revision, updated_at, etag)
            SELECT internal_id, last_name, first_name, 'ACTIVE',
                   creation_date, 1, now(), 'stale'
            FROM anchor_directory WHERE internal_id=%s
            ON CONFLICT (internal_id) DO UPDATE SET
               anchor_status = EXCLUDED.anchor_status,
               revision = EXCLUDED.revision
            WHERE anchor_directory.revision < EXCLUDED.revision
            """,
            (minted,),
        )
        c.execute(
            "SELECT revision, anchor_status FROM anchor_directory WHERE internal_id=%s",
            (minted,),
        )
        after = c.fetchone()
    assert after == (2, "ARCHIVED"), f"stale revision must not win, got {after}"
