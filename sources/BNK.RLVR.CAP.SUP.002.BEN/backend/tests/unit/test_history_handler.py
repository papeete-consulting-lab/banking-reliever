"""Unit tests for GetAnchorHistoryHandler (TASK-006).

Validates:

  1. Missing anchor (no rows at all) → AnchorNotFound (→ 404).
  2. since_revision strict-greater-than semantics.
  3. since_revision past the tail with rows in the projection → empty
     list, NOT 404 (the anchor exists, the caller polled past the tail).
  4. Ill-formed UUIDv7 → AnchorNotFound.
  5. PSEUDONYMISED row survives — handler returns the full sequence,
     PSEUDONYMISED last, with its right_exercise_id intact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from reliever_beneficiary_anchor.application.handlers import GetAnchorHistoryHandler
from reliever_beneficiary_anchor.domain.errors import AnchorNotFound


@dataclass
class _ReaderFake:
    rows_by_id: dict[str, list[dict]] = field(default_factory=dict)
    calls: list[tuple[str, int | None]] = field(default_factory=list)

    async def list(
        self,
        *,
        internal_id: str,
        since_revision: int | None = None,
    ) -> list[dict]:
        self.calls.append((internal_id, since_revision))
        rows = self.rows_by_id.get(internal_id, [])
        if since_revision is None:
            return list(rows)
        return [r for r in rows if int(r["revision"]) > since_revision]


def _row(internal_id: str, revision: int, kind: str, *, right_exercise_id: str | None = None) -> dict:
    return {
        "internal_id": internal_id,
        "revision": revision,
        "transition_kind": kind,
        "command_id": f"018f8e10-cccc-7000-8000-{revision:012d}",
        "right_exercise_id": right_exercise_id,
        "actor": {"kind": "human", "subject": "018f8e10-2222-7000-8000-000000000001"},
        "occurred_at": datetime(2026, 6, 1, 12, revision, 0, tzinfo=timezone.utc),
    }


_IID = "018f8e10-9999-7000-8000-000000000001"


@pytest.mark.asyncio
async def test_no_rows_raises_anchor_not_found() -> None:
    reader = _ReaderFake()
    h = GetAnchorHistoryHandler(reader=reader)
    with pytest.raises(AnchorNotFound):
        await h.handle(internal_id=_IID)


@pytest.mark.asyncio
async def test_full_lifecycle_returns_ordered_rows() -> None:
    reader = _ReaderFake(
        rows_by_id={
            _IID: [
                _row(_IID, 1, "MINTED"),
                _row(_IID, 2, "UPDATED"),
                _row(_IID, 3, "ARCHIVED"),
                _row(_IID, 4, "RESTORED"),
                _row(
                    _IID,
                    5,
                    "PSEUDONYMISED",
                    right_exercise_id="018f8e10-eeee-7000-8000-000000000001",
                ),
            ]
        }
    )
    h = GetAnchorHistoryHandler(reader=reader)
    result = await h.handle(internal_id=_IID)
    assert [r.revision for r in result.rows] == [1, 2, 3, 4, 5]
    assert [r.transition_kind for r in result.rows] == [
        "MINTED",
        "UPDATED",
        "ARCHIVED",
        "RESTORED",
        "PSEUDONYMISED",
    ]
    # PSEUDONYMISED row carries the right_exercise_id — the GDPR-fulfilment
    # proof.
    assert result.rows[-1].right_exercise_id == (
        "018f8e10-eeee-7000-8000-000000000001"
    )
    # No PII field surfaces in the typed row.
    keys = result.rows[0].to_dict().keys()
    for forbidden in ("last_name", "first_name", "date_of_birth", "contact_details"):
        assert forbidden not in keys


@pytest.mark.asyncio
async def test_since_revision_strict_filter() -> None:
    reader = _ReaderFake(
        rows_by_id={
            _IID: [_row(_IID, r, "UPDATED") for r in range(1, 6)],
        }
    )
    h = GetAnchorHistoryHandler(reader=reader)
    result = await h.handle(internal_id=_IID, since_revision=2)
    assert [r.revision for r in result.rows] == [3, 4, 5]


@pytest.mark.asyncio
async def test_since_revision_past_tail_returns_empty_not_404() -> None:
    """Anchor exists; caller polled past the latest revision — return
    an empty list, NOT 404.
    """
    reader = _ReaderFake(
        rows_by_id={_IID: [_row(_IID, 1, "MINTED")]},
    )
    h = GetAnchorHistoryHandler(reader=reader)
    result = await h.handle(internal_id=_IID, since_revision=99)
    assert result.rows == []


@pytest.mark.asyncio
async def test_ill_formed_uuid_raises_anchor_not_found() -> None:
    reader = _ReaderFake()
    h = GetAnchorHistoryHandler(reader=reader)
    with pytest.raises(AnchorNotFound):
        await h.handle(internal_id="not-a-uuid")
