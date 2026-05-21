"""JWT extraction unit tests — decode-only, no signature verification."""

from __future__ import annotations

import base64
import json

from reliever_beneficiary_anchor.infrastructure.security.jwt import actor_from_bearer


def _make_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"sig").rstrip(b"=").decode()
    return f"{header}.{body}.{sig}"


def test_missing_header_yields_system_anonymous():
    actor = actor_from_bearer(None)
    assert actor.kind == "system"
    assert actor.subject == "system:anonymous"


def test_bearer_with_sub_yields_human_actor():
    token = _make_jwt({"sub": "018f8e10-2222-7000-8000-000000000001"})
    actor = actor_from_bearer(f"Bearer {token}")
    assert actor.kind == "human"
    assert actor.subject == "018f8e10-2222-7000-8000-000000000001"


def test_bearer_with_actor_kind_service():
    token = _make_jwt({"sub": "CAP.SUP.001.RET", "actor_kind": "service"})
    actor = actor_from_bearer(f"Bearer {token}")
    assert actor.kind == "service"
    assert actor.subject == "CAP.SUP.001.RET"


def test_bearer_with_on_behalf_of():
    token = _make_jwt({
        "sub": "CAP.SUP.001.RET",
        "actor_kind": "service",
        "on_behalf_of": "018f8e10-3333-7000-8000-000000000001",
    })
    actor = actor_from_bearer(f"Bearer {token}")
    assert actor.on_behalf_of == "018f8e10-3333-7000-8000-000000000001"


def test_garbage_token_falls_back_to_system_anonymous():
    actor = actor_from_bearer("Bearer NOT-A-TOKEN")
    assert actor.kind == "system"
