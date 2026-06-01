"""Unit tests for compute_history_etag (TASK-006)."""

from __future__ import annotations

from datetime import datetime, timezone

from reliever_beneficiary_anchor.infrastructure.persistence.history import (
    compute_history_etag,
)


def _row(internal_id: str, revision: int) -> dict:
    return {
        "internal_id": internal_id,
        "revision": revision,
        "transition_kind": "UPDATED",
        "occurred_at": datetime(2026, 6, 1, 12, revision, 0, tzinfo=timezone.utc),
    }


def test_etag_is_weak_and_24_hex_chars() -> None:
    rows = [_row("018f8e10-9999-7000-8000-000000000001", 1)]
    etag = compute_history_etag(rows)
    assert etag.startswith('W/"') and etag.endswith('"')
    inner = etag[3:-1]
    assert len(inner) == 24
    assert all(c in "0123456789abcdef" for c in inner)


def test_etag_changes_when_new_row_arrives() -> None:
    iid = "018f8e10-9999-7000-8000-000000000001"
    rows_v1 = [_row(iid, 1)]
    rows_v2 = [_row(iid, 1), _row(iid, 2)]
    assert compute_history_etag(rows_v1) != compute_history_etag(rows_v2)


def test_etag_stable_when_rows_unchanged() -> None:
    iid = "018f8e10-9999-7000-8000-000000000001"
    rows = [_row(iid, 1), _row(iid, 2), _row(iid, 3)]
    assert compute_history_etag(rows) == compute_history_etag(list(rows))


def test_etag_differs_per_anchor() -> None:
    rows_a = [_row("018f8e10-9999-7000-8000-000000000001", 1)]
    rows_b = [_row("018f8e10-9999-7000-8000-000000000002", 1)]
    assert compute_history_etag(rows_a) != compute_history_etag(rows_b)


def test_empty_rows_returns_defensive_marker() -> None:
    assert compute_history_etag([]) == 'W/"empty"'
