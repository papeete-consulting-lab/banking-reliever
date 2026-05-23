"""DoD criteria reached only at the live HTTP+DB boundary:
  #3/#5 PSEUDONYMISED guards (no HTTP mint path to PSEUDONYMISED in TASK-004;
        we seed the store directly to reach the terminal state)
  #7   idempotent replay writes NO second outbox row (DB-level count)
  #8   each successful transition produces exactly one outbox row (DB-level)
"""

from __future__ import annotations

import time

from conftest import BASE, uuidv7


def _outbox_count(pg, internal_id: str) -> int:
    with pg.cursor() as c:
        c.execute(
            "SELECT count(*) FROM outbox WHERE payload->>'internal_id' = %s",
            (internal_id,),
        )
        return c.fetchone()[0]


def _seed_pseudonymised(pg) -> str:
    iid = uuidv7()
    with pg.cursor() as c:
        c.execute(
            """
            INSERT INTO anchor
              (internal_id, last_name, first_name, date_of_birth, contact_details,
               anchor_status, creation_date, pseudonymized_at, revision)
            VALUES (%s, NULL, NULL, NULL, NULL, 'PSEUDONYMISED',
                    current_date, now(), 4)
            """,
            (iid,),
        )
    return iid


# ─── DoD #3 / #5 — PSEUDONYMISED is terminal for both verbs ──────────────


def test_archive_on_pseudonymised_returns_409(rest, pg):
    """DoD #3: ARCHIVE rejects 409 ANCHOR_PSEUDONYMISED when PSEUDONYMISED."""
    iid = _seed_pseudonymised(pg)
    r = rest.post(
        f"{BASE}/anchors/{iid}/archive",
        json={"command_id": uuidv7(), "reason": "PROGRAMME_EXIT_SUCCESS"},
        timeout=10,
    )
    assert r.status_code == 409, r.text
    assert r.json()["error_code"] == "ANCHOR_PSEUDONYMISED"


def test_restore_on_pseudonymised_returns_409(rest, pg):
    """DoD #5: RESTORE rejects 409 ANCHOR_PSEUDONYMISED when PSEUDONYMISED."""
    iid = _seed_pseudonymised(pg)
    r = rest.post(
        f"{BASE}/anchors/{iid}/restore",
        json={"command_id": uuidv7(), "reason": "ARCHIVED_IN_ERROR"},
        timeout=10,
    )
    assert r.status_code == 409, r.text
    assert r.json()["error_code"] == "ANCHOR_PSEUDONYMISED"


# ─── DoD #8 — exactly one outbox row per successful transition ───────────


def test_archive_then_restore_two_outbox_rows(rest, pg, minted):
    """DoD #8: ARCHIVE then RESTORE leave exactly two outbox rows for the
    anchor (one per transition); MINT's row is excluded by filtering on the
    transition payloads."""
    before = _outbox_count(pg, minted)  # includes the MINT row
    rest.post(
        f"{BASE}/anchors/{minted}/archive",
        json={"command_id": uuidv7(), "reason": "PROGRAMME_EXIT_SUCCESS"},
        timeout=10,
    )
    rest.post(
        f"{BASE}/anchors/{minted}/restore",
        json={"command_id": uuidv7(), "reason": "REINSTATED_AFTER_REVIEW"},
        timeout=10,
    )
    after = _outbox_count(pg, minted)
    assert after - before == 2, f"expected +2 outbox rows, got +{after - before}"


# ─── DoD #7 — idempotent replay writes no second outbox row ──────────────


def test_archive_replay_no_second_outbox_row(rest, pg, minted):
    """DoD #7: a duplicate command_id returns 200 + COMMAND_ALREADY_PROCESSED
    and does NOT append a second outbox row."""
    cid = uuidv7()
    r1 = rest.post(
        f"{BASE}/anchors/{minted}/archive",
        json={"command_id": cid, "reason": "PROGRAMME_EXIT_SUCCESS"},
        timeout=10,
    )
    assert r1.status_code == 200, r1.text
    count_after_first = _outbox_count(pg, minted)

    r2 = rest.post(
        f"{BASE}/anchors/{minted}/archive",
        json={"command_id": cid, "reason": "PROGRAMME_EXIT_SUCCESS"},
        timeout=10,
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    # prior snapshot + COMMAND_ALREADY_PROCESSED marker
    assert body.get("error_code") == "COMMAND_ALREADY_PROCESSED", body
    snap = body.get("anchor", body)
    assert snap["anchor_status"] == "ARCHIVED"
    assert snap["revision"] == 2

    count_after_replay = _outbox_count(pg, minted)
    assert count_after_replay == count_after_first, "replay must not append an outbox row"
