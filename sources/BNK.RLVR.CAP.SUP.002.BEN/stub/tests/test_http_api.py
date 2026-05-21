"""HTTP contract tests — exercise both query endpoints declared in
``process/BNK.RLVR.CAP.SUP.002.BEN/api.yaml``.

The publisher half is force-disabled (``RELIEVER_STUB_ACTIVE=false``) so no
RabbitMQ connection is required.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from reliever_beneficiary_identity_anchor_stub.app import create_app
from reliever_beneficiary_identity_anchor_stub.settings import get_settings, reset_settings_cache


@pytest.fixture
def client_active(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RELIEVER_STUB_ACTIVE", "false")
    monkeypatch.setenv("RELIEVER_STUB_HTTP_ACTIVE", "true")
    reset_settings_cache()
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_inactive(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RELIEVER_STUB_ACTIVE", "false")
    monkeypatch.setenv("RELIEVER_STUB_HTTP_ACTIVE", "false")
    reset_settings_cache()
    app = create_app()
    with TestClient(app) as c:
        yield c


ACTIVE_ID = "018f8e10-0000-7000-8000-000000000001"
ARCHIVED_ID = "018f8e10-0000-7000-8000-000000000002"
PSEUDO_ID = "018f8e10-0000-7000-8000-000000000003"
UNKNOWN_ID = "018f8e10-9999-7000-8000-000000009999"


# ── health ────────────────────────────────────────────────────────────


def test_health_endpoint_always_alive(client_inactive: TestClient) -> None:
    r = client_inactive.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── GET /anchors/{id} ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "internal_id, expected_status",
    [
        (ACTIVE_ID, "ACTIVE"),
        (ARCHIVED_ID, "ARCHIVED"),
        (PSEUDO_ID, "PSEUDONYMISED"),
    ],
)
def test_get_anchor_returns_canned_payload(
    client_active: TestClient, internal_id: str, expected_status: str
) -> None:
    r = client_active.get(f"/anchors/{internal_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["internal_id"] == internal_id
    assert body["anchor_status"] == expected_status
    # ETag + Cache-Control per api.yaml
    assert "ETag" in r.headers
    assert r.headers["Cache-Control"] == "max-age=60"


def test_get_anchor_pseudonymised_pii_is_null(client_active: TestClient) -> None:
    r = client_active.get(f"/anchors/{PSEUDO_ID}")
    body = r.json()
    assert body["last_name"] is None
    assert body["first_name"] is None
    assert body["date_of_birth"] is None
    assert body["contact_details"] is None
    assert body["pseudonymized_at"] is not None
    assert body["internal_id"] == PSEUDO_ID  # still resolvable


def test_get_anchor_unknown_returns_404(client_active: TestClient) -> None:
    r = client_active.get(f"/anchors/{UNKNOWN_ID}")
    assert r.status_code == 404
    assert r.json()["detail"] == "ANCHOR_NOT_FOUND"


def test_get_anchor_304_on_etag_match(client_active: TestClient) -> None:
    r1 = client_active.get(f"/anchors/{ACTIVE_ID}")
    etag = r1.headers["ETag"]
    r2 = client_active.get(f"/anchors/{ACTIVE_ID}", headers={"If-None-Match": etag})
    assert r2.status_code == 304
    # Body must be empty on 304
    assert r2.content == b""


def test_get_anchor_returns_200_when_etag_mismatch(client_active: TestClient) -> None:
    r = client_active.get(f"/anchors/{ACTIVE_ID}", headers={"If-None-Match": 'W/"stale"'})
    assert r.status_code == 200


# ── GET /anchors/{id}/history ─────────────────────────────────────────


def test_get_history_returns_canned_rows(client_active: TestClient) -> None:
    r = client_active.get(f"/anchors/{PSEUDO_ID}/history")
    assert r.status_code == 200
    body = r.json()
    assert body["internal_id"] == PSEUDO_ID
    assert len(body["rows"]) == 5
    assert r.headers["Cache-Control"] == "max-age=0"
    assert "ETag" in r.headers
    # PII-free by construction
    for row in body["rows"]:
        assert set(row.keys()) <= {
            "revision",
            "transition_kind",
            "command_id",
            "right_exercise_id",
            "actor",
            "occurred_at",
        }


def test_get_history_supports_since_revision(client_active: TestClient) -> None:
    r = client_active.get(f"/anchors/{PSEUDO_ID}/history?since_revision=3")
    assert r.status_code == 200
    body = r.json()
    assert [row["revision"] for row in body["rows"]] == [4, 5]


def test_get_history_unknown_returns_404(client_active: TestClient) -> None:
    r = client_active.get(f"/anchors/{UNKNOWN_ID}/history")
    assert r.status_code == 404
    assert r.json()["detail"] == "ANCHOR_NOT_FOUND"


def test_get_history_304_on_etag_match(client_active: TestClient) -> None:
    r1 = client_active.get(f"/anchors/{ARCHIVED_ID}/history")
    etag = r1.headers["ETag"]
    r2 = client_active.get(
        f"/anchors/{ARCHIVED_ID}/history", headers={"If-None-Match": etag}
    )
    assert r2.status_code == 304


# ── STUB_HTTP_ACTIVE=false ────────────────────────────────────────────


def test_anchors_routes_503_when_http_inactive(client_inactive: TestClient) -> None:
    r1 = client_inactive.get(f"/anchors/{ACTIVE_ID}")
    assert r1.status_code == 503
    r2 = client_inactive.get(f"/anchors/{ACTIVE_ID}/history")
    assert r2.status_code == 503
    # /health remains 200
    r3 = client_inactive.get("/health")
    assert r3.status_code == 200
