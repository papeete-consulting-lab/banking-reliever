"""UUIDv7 helpers and envelope assembly.

ADR-TECH-STRAT-007 mandates UUIDv7 for every bus message envelope. The
Python stdlib (3.12) doesn't ship a UUIDv7 generator, so we implement
RFC 9562 §5.7 directly — it is ~25 lines and the alternative would be
pinning a third-party wheel just for an identifier.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from .config import EMITTING_CAPABILITY


def uuid7() -> uuid.UUID:
    """Return a fresh UUIDv7 per RFC 9562 §5.7.

    Layout:
      48 bits — unix timestamp in milliseconds (big-endian)
       4 bits — version (0b0111 = 7)
      12 bits — rand_a (cryptographic random)
       2 bits — variant (0b10)
      62 bits — rand_b (cryptographic random)
    """
    # 48-bit ms timestamp.
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    # 10 random bytes — 80 bits, of which 12 go into rand_a and 62 into rand_b.
    rand = int.from_bytes(os.urandom(10), "big")
    rand_a = (rand >> 64) & 0x0FFF        # 12 bits
    rand_b = rand & 0x3FFFFFFFFFFFFFFF    # 62 bits

    version = 0x7
    variant = 0x2  # 0b10

    value = (ms & 0xFFFFFFFFFFFF) << 80
    value |= version << 76
    value |= rand_a << 64
    value |= variant << 62
    value |= rand_b

    return uuid.UUID(int=value)


def uuid7_str() -> str:
    return str(uuid7())


def now_iso8601() -> str:
    """RFC 3339 timestamp with millisecond precision and explicit UTC offset.

    The schemas require `format: date-time`. We use `isoformat(timespec="milliseconds")`
    so the output is stable and easy to read in logs.
    """
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=(datetime.now(timezone.utc).microsecond // 1000) * 1000)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def build_envelope(
    *,
    correlation_id: str,
    causation_id: str,
    schema_version: str,
) -> dict[str, Any]:
    """Return a fully-populated envelope dict for a bus message.

    Per the canonical schemas:
      - message_id, correlation_id, causation_id are UUIDv7 strings
      - emitting_capability is constant "BNK.RLVR.CAP.BSP.001.SCO"
      - schema_version is semver
      - emitted_at is RFC 3339
    """
    return {
        "message_id": uuid7_str(),
        "schema_version": schema_version,
        "emitted_at": now_iso8601(),
        "emitting_capability": EMITTING_CAPABILITY,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
    }
