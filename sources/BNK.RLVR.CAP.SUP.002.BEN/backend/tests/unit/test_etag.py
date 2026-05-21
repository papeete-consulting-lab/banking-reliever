from __future__ import annotations

from reliever_beneficiary_anchor.infrastructure.persistence.projection import compute_etag


def test_etag_is_deterministic_for_same_revision():
    a = compute_etag("018f8e10-aaaa-7000-8000-000000000001", 1)
    b = compute_etag("018f8e10-aaaa-7000-8000-000000000001", 1)
    assert a == b


def test_etag_changes_on_revision_bump():
    a = compute_etag("018f8e10-aaaa-7000-8000-000000000001", 1)
    b = compute_etag("018f8e10-aaaa-7000-8000-000000000001", 2)
    assert a != b


def test_etag_changes_on_internal_id():
    a = compute_etag("018f8e10-aaaa-7000-8000-000000000001", 1)
    b = compute_etag("018f8e10-aaaa-7000-8000-000000000002", 1)
    assert a != b


def test_etag_is_weak_quoted():
    e = compute_etag("018f8e10-aaaa-7000-8000-000000000001", 1)
    assert e.startswith('W/"')
    assert e.endswith('"')
