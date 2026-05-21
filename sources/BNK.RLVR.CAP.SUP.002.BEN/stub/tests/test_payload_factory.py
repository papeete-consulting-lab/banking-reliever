"""Test the payload factory — every transition kind produces a payload that
validates against the RVT JSON Schema authored under /process.

This is the DoD's contract-validation acceptance — no broker required.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest

from reliever_beneficiary_identity_anchor_stub.payload_factory import (
    TRANSITION_KINDS,
    TransitionCycler,
    build_all_kinds,
    build_event,
    uuid7,
    uuid7_str,
)
from reliever_beneficiary_identity_anchor_stub.schema_validator import (
    SchemaValidationError,
    validate,
)
from reliever_beneficiary_identity_anchor_stub.settings import get_settings


SCHEMA_PATH = get_settings().rvt_schema_path
UUIDV7_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def test_schema_file_exists() -> None:
    """The vendored RVT schema snapshot must be reachable from the stub."""
    assert SCHEMA_PATH.is_file(), f"Schema not found at {SCHEMA_PATH}"


# ── UUIDv7 plumbing ────────────────────────────────────────────────────


def test_uuid7_is_version_7_and_variant_rfc4122() -> None:
    for _ in range(50):
        u = uuid7()
        # version must be 7
        assert u.version == 7
        # variant bits must be 10xx (RFC 4122)
        assert u.variant == uuid.RFC_4122


def test_uuid7_string_matches_pattern() -> None:
    for _ in range(50):
        assert UUIDV7_RE.match(uuid7_str()) is not None


def test_uuid7_is_monotonic_enough() -> None:
    """UUIDv7 encodes a millisecond timestamp in its first 48 bits — back-to-back
    calls within the same ms may collide on the timestamp prefix, but across
    ~10 ms windows the prefix must be non-decreasing.
    """
    import time

    samples = []
    for _ in range(5):
        samples.append(uuid7().int >> 80)
        time.sleep(0.005)
    assert samples == sorted(samples)


# ── per-kind schema validation ─────────────────────────────────────────


@pytest.mark.parametrize("kind", TRANSITION_KINDS)
def test_build_event_validates_against_rvt_schema(kind: str) -> None:
    payload = build_event(transition_kind=kind)
    # Will raise SchemaValidationError on drift; otherwise the call is a no-op.
    validate(payload, SCHEMA_PATH, schema_id="BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED")


@pytest.mark.parametrize("kind", TRANSITION_KINDS)
def test_envelope_has_uuidv7_trio(kind: str) -> None:
    payload = build_event(transition_kind=kind)
    env = payload["envelope"]
    for field in ("message_id", "correlation_id", "causation_id"):
        assert UUIDV7_RE.match(env[field]), (
            f"{field} for kind={kind} is not a valid UUIDv7: {env[field]!r}"
        )
    assert env["emitting_capability"] == "BNK.RLVR.CAP.SUP.002.BEN"
    assert env["schema_version"] == "0.1.0"


def test_pseudonymised_branch_is_exercised() -> None:
    """The conditional `if/then` for PSEUDONYMISED — PII null + required pseudo fields."""
    payload = build_event(transition_kind="PSEUDONYMISED")
    assert payload["anchor_status"] == "PSEUDONYMISED"
    assert payload["last_name"] is None
    assert payload["first_name"] is None
    assert payload["date_of_birth"] is None
    assert payload["contact_details"] is None
    assert UUIDV7_RE.match(payload["right_exercise_id"])
    assert payload["pseudonymized_at"] is not None
    # Schema must accept it.
    validate(payload, SCHEMA_PATH, schema_id="BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED")


def test_minted_updated_restored_keep_pii() -> None:
    for kind in ("MINTED", "UPDATED", "RESTORED"):
        payload = build_event(transition_kind=kind)
        assert payload["anchor_status"] == "ACTIVE"
        assert payload["pseudonymized_at"] is None
        assert isinstance(payload["last_name"], str)
        assert isinstance(payload["first_name"], str)
        assert isinstance(payload["date_of_birth"], str)


def test_archived_keeps_pii_but_status_changes() -> None:
    payload = build_event(transition_kind="ARCHIVED")
    assert payload["anchor_status"] == "ARCHIVED"
    assert payload["pseudonymized_at"] is None
    assert isinstance(payload["last_name"], str)


def test_build_all_kinds_covers_all_five() -> None:
    payloads = build_all_kinds()
    kinds = {p["transition_kind"] for p in payloads}
    assert kinds == set(TRANSITION_KINDS)
    # Every payload validates.
    for p in payloads:
        validate(p, SCHEMA_PATH, schema_id="BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED")


def test_invalid_kind_rejected() -> None:
    with pytest.raises(ValueError):
        build_event(transition_kind="MUTATED")


def test_validator_fails_on_corrupt_payload() -> None:
    payload = build_event(transition_kind="MINTED")
    # Break the schema constraint: missing required field.
    payload.pop("internal_id")
    with pytest.raises(SchemaValidationError):
        validate(payload, SCHEMA_PATH, schema_id="BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED")


# ── transition cycler ─────────────────────────────────────────────────


def test_transition_cycler_visits_all_kinds_then_repeats() -> None:
    cycler = TransitionCycler()
    visited = [cycler.next_kind() for _ in range(10)]
    assert visited[:5] == list(TRANSITION_KINDS)
    assert visited[5:] == list(TRANSITION_KINDS)
