"""ADR-TECH-STRAT-007 — every emitted bus message carries the UUIDv7
envelope trio (message_id, correlation_id, causation_id).

We assert format compliance and the semantic rules:
  - correlation_id  == case_id (the aggregate identity)
  - causation_id    == upstream trigger event_id, for recomputation flows
                       (for ENTRY, causation_id is a synthetic UUIDv7
                       standing in for the CMD.COMPUTE_ENTRY_SCORE request_id)
"""
from __future__ import annotations

import re
import uuid

import pytest

from bsp_sco_stub.envelope import build_envelope, now_iso8601, uuid7, uuid7_str
from bsp_sco_stub.fixtures import (
    build_entry_score_event,
    build_recomputation_emissions,
    make_case_pool,
)


UUIDV7_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
)


def test_uuid7_is_valid_uuid_with_version_7():
    u = uuid7()
    assert isinstance(u, uuid.UUID)
    assert u.version == 7
    assert UUIDV7_RE.match(str(u)), str(u)


def test_uuid7_str_collision_free_over_many_samples():
    seen = {uuid7_str() for _ in range(2000)}
    assert len(seen) == 2000


def test_now_iso8601_is_rfc3339_z_millis():
    ts = now_iso8601()
    assert DATETIME_RE.match(ts), ts


def test_build_envelope_has_all_required_fields():
    case_id = uuid7_str()
    causation = uuid7_str()
    env = build_envelope(
        correlation_id=case_id, causation_id=causation, schema_version="0.2.0"
    )
    assert env["emitting_capability"] == "BNK.RLVR.CAP.BSP.001.SCO"
    assert env["schema_version"] == "0.2.0"
    assert env["correlation_id"] == case_id
    assert env["causation_id"] == causation
    assert UUIDV7_RE.match(env["message_id"])
    assert DATETIME_RE.match(env["emitted_at"])


@pytest.mark.parametrize("force_threshold", [False, True])
def test_recomputation_envelopes_have_uuidv7_trio(cfg, rng, force_threshold):
    pool = make_case_pool(size=2, rng=rng)
    pool[0].has_entry_score = True

    emissions = build_recomputation_emissions(
        case=pool[0], cfg=cfg, rng=rng, force_threshold=force_threshold
    )
    for em in emissions:
        env = em.payload["envelope"]
        assert UUIDV7_RE.match(env["message_id"])
        assert UUIDV7_RE.match(env["correlation_id"])
        assert UUIDV7_RE.match(env["causation_id"])
        # correlation_id == case_id (semantic rule for score-flow events)
        assert env["correlation_id"] == em.payload["case_id"]
        # causation_id == trigger.event_id (semantic rule for recomputation)
        assert env["causation_id"] == em.payload["trigger"]["event_id"]
        # Every message_id is fresh.
        assert env["message_id"] != env["correlation_id"]
        assert env["message_id"] != env["causation_id"]


def test_entry_envelope_has_uuidv7_trio(cfg, rng):
    pool = make_case_pool(size=2, rng=rng)
    em = build_entry_score_event(case=pool[0], cfg=cfg, rng=rng)
    env = em.payload["envelope"]
    assert UUIDV7_RE.match(env["message_id"])
    assert UUIDV7_RE.match(env["correlation_id"])
    assert UUIDV7_RE.match(env["causation_id"])
    assert env["correlation_id"] == em.payload["case_id"]
    # ENTRY's causation_id stands for the synthetic CMD.COMPUTE_ENTRY_SCORE
    # request_id; it should be UUIDv7 but unrelated to case_id.
    assert env["causation_id"] != env["correlation_id"]


def test_all_three_message_ids_in_a_pair_are_distinct(cfg, rng):
    pool = make_case_pool(size=1, rng=rng)
    pool[0].has_entry_score = True

    ems = build_recomputation_emissions(
        case=pool[0], cfg=cfg, rng=rng, force_threshold=True
    )
    ids = [em.payload["envelope"]["message_id"] for em in ems]
    assert len(set(ids)) == len(ids), "message_id collisions in a pair"
