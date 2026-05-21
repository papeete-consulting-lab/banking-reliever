"""Every kind of outgoing payload validates against its canonical schema.

This is the headline DoD assertion of TASK-002. We generate hundreds of
randomised payloads for each of the three RVTs and verify that the
validator accepts every one. We also verify that the validator REJECTS
deliberately-corrupted payloads — otherwise the test would be vacuous.
"""
from __future__ import annotations

import copy
import random

import pytest
from jsonschema.exceptions import ValidationError

from bsp_sco_stub.fixtures import (
    Emission,
    build_entry_score_event,
    build_recomputation_emissions,
    make_case_pool,
    next_emissions,
)


N_SAMPLES = 200


def _emit_one(*, kind: str, pool, cfg, rng) -> list[Emission]:
    case = rng.choice(pool)
    if kind == "ENTRY":
        return [build_entry_score_event(case=case, cfg=cfg, rng=rng)]
    if kind == "RECOMPUTE":
        case.has_entry_score = True  # skip baseline
        return build_recomputation_emissions(case=case, cfg=cfg, rng=rng)
    if kind == "THRESHOLD":
        case.has_entry_score = True
        return build_recomputation_emissions(
            case=case, cfg=cfg, rng=rng, force_threshold=True
        )
    raise AssertionError(kind)


@pytest.mark.parametrize("kind", ["ENTRY", "RECOMPUTE", "THRESHOLD"])
def test_payloads_validate_against_canonical_schema(kind, validator, cfg, rng):
    pool = make_case_pool(size=cfg.case_pool_size, rng=rng)

    seen_rvts: set[str] = set()
    for _ in range(N_SAMPLES):
        emissions = _emit_one(kind=kind, pool=pool, cfg=cfg, rng=rng)
        for em in emissions:
            seen_rvts.add(em.rvt_id)
            validator.validate(em.rvt_id, em.payload)

    if kind == "ENTRY":
        assert seen_rvts == {"BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED"}
    elif kind == "THRESHOLD":
        assert seen_rvts == {
            "BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED",
            "BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED",
        }
    else:  # RECOMPUTE
        # CURRENT is always present; THRESHOLD may or may not be present
        # depending on whether a crossing happened or the probabilistic
        # injection fired.
        assert "BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED" in seen_rvts


def test_corrupted_entry_payload_is_rejected(validator, cfg, rng):
    """If we tamper with a payload, the validator must reject it.

    Without this, the green path test above could be vacuous (e.g. if
    the validator silently swallowed errors).
    """
    pool = make_case_pool(size=2, rng=rng)
    em = build_entry_score_event(case=pool[0], cfg=cfg, rng=rng)

    # 1) Wrong evaluation_type — schema says const "INITIAL".
    bad = copy.deepcopy(em.payload)
    bad["evaluation_type"] = "CURRENT"
    with pytest.raises(ValidationError):
        validator.validate(em.rvt_id, bad)

    # 2) Missing required field.
    bad = copy.deepcopy(em.payload)
    del bad["score_value"]
    with pytest.raises(ValidationError):
        validator.validate(em.rvt_id, bad)

    # 3) Bad envelope.message_id (not UUIDv7).
    bad = copy.deepcopy(em.payload)
    bad["envelope"]["message_id"] = "not-a-uuid"
    with pytest.raises(ValidationError):
        validator.validate(em.rvt_id, bad)

    # 4) Additional property — schemas are additionalProperties:false.
    bad = copy.deepcopy(em.payload)
    bad["unexpected_field"] = "nope"
    with pytest.raises(ValidationError):
        validator.validate(em.rvt_id, bad)


def test_threshold_payload_carries_threshold_metadata(validator, cfg, rng):
    pool = make_case_pool(size=4, rng=rng)
    for case in pool:
        case.has_entry_score = True

    found = False
    for _ in range(50):
        ems = build_recomputation_emissions(
            case=rng.choice(pool), cfg=cfg, rng=rng, force_threshold=True
        )
        thresholds = [e for e in ems if e.rvt_id == "BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED"]
        assert thresholds, "force_threshold=True must produce a threshold emission"
        for t in thresholds:
            validator.validate(t.rvt_id, t.payload)
            assert {"value", "tier_from", "tier_to"} <= set(t.payload["threshold"])
            assert t.payload["direction"] in {"UPWARD", "DOWNWARD"}
            found = True
    assert found
