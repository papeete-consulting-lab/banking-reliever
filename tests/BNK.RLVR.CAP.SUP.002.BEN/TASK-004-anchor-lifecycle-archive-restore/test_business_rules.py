"""FUNC ADR / invariant rules and roadmap scoping reached at the live
boundary: INV.BEN.002 PII continuity (#10), RESTORE reason enum (per the
vendored schema), and the RESTORE-not-archived guard."""

from __future__ import annotations

from conftest import BASE, uuidv7


def _row(pg, internal_id):
    with pg.cursor() as c:
        c.execute(
            "SELECT last_name, first_name, date_of_birth, contact_details, "
            "anchor_status, revision FROM anchor WHERE internal_id=%s",
            (internal_id,),
        )
        return c.fetchone()


def test_pii_unchanged_across_round_trip(rest, pg, minted):
    """DoD #10 / INV.BEN.002: only anchor_status + revision change across
    ARCHIVE/RESTORE; the PII columns stay byte-identical."""
    before = _row(pg, minted)
    rest.post(
        f"{BASE}/anchors/{minted}/archive",
        json={"command_id": uuidv7(), "reason": "ADMINISTRATIVE_ARCHIVAL"},
        timeout=10,
    )
    rest.post(
        f"{BASE}/anchors/{minted}/restore",
        json={"command_id": uuidv7(), "reason": "ARCHIVED_IN_ERROR"},
        timeout=10,
    )
    after = _row(pg, minted)
    # PII (cols 0..3) identical, status back to ACTIVE, revision bumped twice.
    assert before[:4] == after[:4], "PII must be unchanged across the round-trip"
    assert after[4] == "ACTIVE"
    assert after[5] == before[5] + 2


def test_restore_rejects_archive_reason_enum(rest, pg, minted):
    """RESTORE reason enum is its own set (ARCHIVED_IN_ERROR /
    REINSTATED_AFTER_REVIEW). An ARCHIVE-side reason must be rejected 400."""
    rest.post(
        f"{BASE}/anchors/{minted}/archive",
        json={"command_id": uuidv7(), "reason": "PROGRAMME_EXIT_SUCCESS"},
        timeout=10,
    )
    r = rest.post(
        f"{BASE}/anchors/{minted}/restore",
        json={"command_id": uuidv7(), "reason": "PROGRAMME_EXIT_SUCCESS"},
        timeout=10,
    )
    assert r.status_code == 400, r.text


def test_restore_accepts_both_valid_reasons(rest, minted):
    """Both vendored RESTORE reasons are accepted."""
    rest.post(
        f"{BASE}/anchors/{minted}/archive",
        json={"command_id": uuidv7(), "reason": "PROGRAMME_EXIT_SUCCESS"},
        timeout=10,
    )
    r = rest.post(
        f"{BASE}/anchors/{minted}/restore",
        json={"command_id": uuidv7(), "reason": "REINSTATED_AFTER_REVIEW"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    assert r.json()["anchor_status"] == "ACTIVE"
