"""Lightweight tone/vocabulary heuristics on the error surface. Soft hints,
not hard gates — a miss is worth a human look, not a build break."""

from __future__ import annotations

from conftest import BASE, uuidv7


def test_error_uses_domain_vocabulary_not_raw_exceptions(rest):
    """409/404 bodies should speak the anchor lifecycle domain language and
    not leak raw exception types or stack frames."""
    r = rest.post(
        f"{BASE}/anchors/{uuidv7()}/restore",
        json={"command_id": uuidv7(), "reason": "ARCHIVED_IN_ERROR"},
        timeout=10,
    )
    assert r.status_code == 404
    body = r.text.lower()
    assert "anchor" in body
    for leak in ("traceback", "psycopg", "keyerror", "valueerror", "exception("):
        assert leak not in body, f"raw internal token leaked: {leak}"
