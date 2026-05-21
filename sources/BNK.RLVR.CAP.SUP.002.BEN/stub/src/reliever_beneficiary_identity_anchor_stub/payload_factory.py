"""Synthetic payload factory — produces ``BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED``
payloads covering all 5 transition_kind values declared by /process.

Each call to :func:`build_event` rotates through the cycle so the publisher
deterministically exercises the whole schema, including the conditional
``if/then`` branch for ``PSEUDONYMISED`` (PII fields null, ``pseudonymized_at``
+ ``right_exercise_id`` required).

UUIDv7 generation honours ADR-TECH-STRAT-007 Rule 4: every published envelope
carries a UUIDv7 ``message_id``, ``correlation_id`` and ``causation_id``.
"""
from __future__ import annotations

import itertools
import os
import random
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Iterator


# ── transition cycle ────────────────────────────────────────────────────
TRANSITION_KINDS: tuple[str, ...] = (
    "MINTED",
    "UPDATED",
    "ARCHIVED",
    "RESTORED",
    "PSEUDONYMISED",
)


# ── UUIDv7 (RFC 9562 §5.7) ──────────────────────────────────────────────
def uuid7() -> uuid.UUID:
    """Generate a UUIDv7 from current millisecond timestamp.

    Reference: RFC 9562 §5.7.
    Layout: 48-bit Unix ms timestamp | version (4 bits, value 7)
            | 12-bit random | variant (2 bits) | 62-bit random.
    """
    ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand_a = random.getrandbits(12)  # 12 bits
    rand_b = random.getrandbits(62)  # 62 bits

    value = (ms & ((1 << 48) - 1)) << 80
    value |= (0x7) << 76  # version 7
    value |= (rand_a & 0xFFF) << 64
    value |= (0b10) << 62  # variant (RFC 4122)
    value |= rand_b & ((1 << 62) - 1)
    return uuid.UUID(int=value)


def uuid7_str() -> str:
    return str(uuid7())


# ── deterministic anchor identities (cycle through fixtures) ────────────
# Fixture anchors live in fixtures/get_anchor.json; the cycler returns one
# of them so a stub run produces a coherent stream that downstream consumers
# can correlate with the query API.
_FIXTURE_ANCHOR_IDS: tuple[str, ...] = (
    # ACTIVE anchor (fixture #1)
    "018f8e10-0000-7000-8000-000000000001",
    # ARCHIVED anchor (fixture #2)
    "018f8e10-0000-7000-8000-000000000002",
    # PSEUDONYMISED anchor (fixture #3)
    "018f8e10-0000-7000-8000-000000000003",
)


# ── transition cycler ──────────────────────────────────────────────────
class TransitionCycler:
    """Round-robin iterator over the 5 transition_kind values.

    The publisher uses :meth:`next_kind` to pick a kind per event so the
    DoD criterion "for each of 5 transition_kind values, publishes ≥ 1
    synthetic event" is satisfied deterministically.
    """

    def __init__(self, kinds: tuple[str, ...] = TRANSITION_KINDS) -> None:
        self._cycle: Iterator[str] = itertools.cycle(kinds)

    def next_kind(self) -> str:
        return next(self._cycle)


# ── pseudo-PII generators ──────────────────────────────────────────────
# Stable synthetic identities — never real PII.
_FIRST_NAMES = ("Alex", "Jordan", "Sam", "Riley", "Casey", "Morgan", "Taylor")
_LAST_NAMES = ("Doe", "Smith", "Martin", "Garcia", "Nguyen", "Dupont")


def _synth_pii_block(seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    return {
        "last_name": rng.choice(_LAST_NAMES),
        "first_name": rng.choice(_FIRST_NAMES),
        "date_of_birth": "1985-06-15",
        "contact_details": {
            "email": "test+stub@example.invalid",
            "phone": "+33100000000",
            "postal_address": {
                "line1": "1 stub street",
                "line2": "apt 0",
                "postal_code": "75001",
                "city": "Paris",
                "country": "FR",
            },
        },
    }


# ── envelope ───────────────────────────────────────────────────────────
def build_envelope(
    *,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    schema_version: str = "0.1.0",
) -> dict[str, Any]:
    """Build a fresh envelope. Every UUID is a freshly-minted UUIDv7."""
    return {
        "message_id": uuid7_str(),
        "schema_version": schema_version,
        "emitted_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "emitting_capability": "BNK.RLVR.CAP.SUP.002.BEN",
        "correlation_id": correlation_id or uuid7_str(),
        "causation_id": causation_id or uuid7_str(),
    }


# ── main builder ───────────────────────────────────────────────────────
def build_event(
    *,
    transition_kind: str,
    internal_id: str | None = None,
    revision: int | None = None,
) -> dict[str, Any]:
    """Construct a single ``BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED`` payload.

    The payload validates against
    ``process/BNK.RLVR.CAP.SUP.002.BEN/schemas/BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json``
    including the conditional ``if/then`` branches.

    Args:
      transition_kind: one of TRANSITION_KINDS.
      internal_id: anchor identifier; defaults to a deterministic fixture id.
      revision: monotonic revision; defaults to a kind-stable integer.
    """
    if transition_kind not in TRANSITION_KINDS:
        raise ValueError(f"unknown transition_kind: {transition_kind!r}")

    # Default to a deterministic fixture anchor that lines up with the query API.
    if internal_id is None:
        internal_id = _FIXTURE_ANCHOR_IDS[TRANSITION_KINDS.index(transition_kind) % 3]

    if revision is None:
        revision = TRANSITION_KINDS.index(transition_kind) + 1

    correlation_id = internal_id  # spec: correlation_id == internal_id for anchor-scoped ops
    causation_id = uuid7_str()

    envelope = build_envelope(
        correlation_id=correlation_id,
        causation_id=causation_id,
    )

    creation_date = "2026-01-15"
    occurred_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    base: dict[str, Any] = {
        "envelope": envelope,
        "internal_id": internal_id,
        "anchor_status": "ACTIVE",
        "creation_date": creation_date,
        "revision": revision,
        "transition_kind": transition_kind,
        "command_id": uuid7_str(),
        "right_exercise_id": None,
        "occurred_at": occurred_at,
        "pseudonymized_at": None,
    }

    # Per-kind shaping — mirrors the schema's allOf/if-then branches.
    if transition_kind == "PSEUDONYMISED":
        base["anchor_status"] = "PSEUDONYMISED"
        base["last_name"] = None
        base["first_name"] = None
        base["date_of_birth"] = None
        base["contact_details"] = None
        base["pseudonymized_at"] = occurred_at
        base["right_exercise_id"] = uuid7_str()
    elif transition_kind == "ARCHIVED":
        base["anchor_status"] = "ARCHIVED"
        base.update(_synth_pii_block(seed=hash(internal_id) & 0xFFFFFFFF))
    else:
        # MINTED / UPDATED / RESTORED → ACTIVE + PII required
        base["anchor_status"] = "ACTIVE"
        base.update(_synth_pii_block(seed=hash(internal_id) & 0xFFFFFFFF))

    return base


def build_all_kinds() -> list[dict[str, Any]]:
    """Build exactly one event per transition_kind — used by the smoke test
    that guarantees ≥1 event per kind is emitted on every publisher pass.
    """
    return [build_event(transition_kind=k) for k in TRANSITION_KINDS]
