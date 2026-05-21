"""Test the canned fixtures load and cover the DoD-required statuses."""
from __future__ import annotations

import pytest

from reliever_beneficiary_identity_anchor_stub.fixture_store import FixtureStore
from reliever_beneficiary_identity_anchor_stub.settings import get_settings


@pytest.fixture(scope="module")
def store() -> FixtureStore:
    settings = get_settings()
    return FixtureStore.load(settings.fixtures_dir)


def test_at_least_three_anchors(store: FixtureStore) -> None:
    assert len(store.anchor_ids()) >= 3


@pytest.mark.parametrize("status", ["ACTIVE", "ARCHIVED", "PSEUDONYMISED"])
def test_each_status_covered(store: FixtureStore, status: str) -> None:
    assert store.anchors_by_status(status), f"No fixture in status {status}"


def test_pseudonymised_fixture_has_null_pii(store: FixtureStore) -> None:
    pseudo = store.anchors_by_status("PSEUDONYMISED")
    assert pseudo, "expected one PSEUDONYMISED fixture"
    a = pseudo[0]
    assert a["last_name"] is None
    assert a["first_name"] is None
    assert a["date_of_birth"] is None
    assert a["contact_details"] is None
    assert a["pseudonymized_at"] is not None
    assert a["internal_id"] is not None  # still resolvable


def test_etags_are_stable(store: FixtureStore) -> None:
    """Two reads on the same fixture must produce the same ETag (used by 304)."""
    aid = store.anchor_ids()[0]
    e1 = store.anchor_etag(aid)
    e2 = store.anchor_etag(aid)
    assert e1 == e2
    assert e1.startswith('W/"')


def test_history_filter_by_since_revision(store: FixtureStore) -> None:
    aid = "018f8e10-0000-7000-8000-000000000003"  # PSEUDONYMISED, 5 rows
    full = store.get_history(aid)
    assert len(full["rows"]) == 5
    after_3 = store.get_history(aid, since_revision=3)
    # rows with revision > 3 → revisions 4 and 5
    assert [r["revision"] for r in after_3["rows"]] == [4, 5]
    after_5 = store.get_history(aid, since_revision=5)
    assert after_5["rows"] == []


def test_history_etag_changes_with_filter(store: FixtureStore) -> None:
    aid = "018f8e10-0000-7000-8000-000000000003"
    e_all = store.history_etag(aid)
    e_filtered = store.history_etag(aid, since_revision=3)
    assert e_all != e_filtered
