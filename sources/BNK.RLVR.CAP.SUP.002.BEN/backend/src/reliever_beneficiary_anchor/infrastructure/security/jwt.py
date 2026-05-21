"""Extract an ``Actor`` from a JWT ``Authorization: Bearer`` header.

Decode-only — signature verification happens at the API gateway. The
service trusts the gateway and uses the ``sub`` claim verbatim.

Missing / invalid token → falls back to ``Actor.system_anonymous()`` so
local development without a gateway still works. In production the
gateway must enforce authentication.
"""

from __future__ import annotations

from typing import Any

import structlog
from jose import jwt
from jose.exceptions import JWTError

from ...domain.value_objects import Actor, ActorKind

log = structlog.get_logger()


def actor_from_bearer(authorization_header: str | None) -> Actor:
    if not authorization_header:
        return Actor.system_anonymous()
    parts = authorization_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return Actor.system_anonymous()
    token = parts[1].strip()
    try:
        claims: dict[str, Any] = jwt.get_unverified_claims(token)
    except JWTError:
        log.warning("jwt.decode_failed")
        return Actor.system_anonymous()

    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        return Actor.system_anonymous()

    raw_kind = claims.get("actor_kind") or claims.get("kind") or "human"
    kind: ActorKind = raw_kind if raw_kind in ("human", "service", "system") else "human"
    on_behalf_of = claims.get("on_behalf_of")
    return Actor(
        kind=kind,
        subject=sub,
        on_behalf_of=on_behalf_of if isinstance(on_behalf_of, str) and on_behalf_of else None,
    )
