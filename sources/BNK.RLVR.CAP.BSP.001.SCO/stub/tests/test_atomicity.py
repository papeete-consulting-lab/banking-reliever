"""INV.SCO.003 — atomicity of threshold detection with recomputation.

When a synthetic recomputation crosses a tier threshold, BOTH
CURRENT_SCORE_RECOMPUTED and SCORE_THRESHOLD_REACHED must be produced in
the SAME emission batch — never one without the other. The two events
must also share the same evaluation_id and trigger.event_id (proof of
atomicity that downstream consumers like BNK.RLVR.CAP.BSP.001.TIE rely on).

Tests also assert that the publisher publishes the pair in a single
publish_emissions call — i.e. the contract is honoured end-to-end, not
just at the fixture level.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from bsp_sco_stub.fixtures import (
    Emission,
    build_recomputation_emissions,
    make_case_pool,
)
from bsp_sco_stub.publisher import Publisher


def test_forced_threshold_emits_pair(cfg, rng):
    pool = make_case_pool(size=3, rng=rng)
    for case in pool:
        case.has_entry_score = True

    ems = build_recomputation_emissions(
        case=pool[0], cfg=cfg, rng=rng, force_threshold=True
    )
    rvts = [e.rvt_id for e in ems]
    assert "BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED" in rvts
    assert "BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED" in rvts


def test_pair_shares_evaluation_id_and_trigger(cfg, rng):
    pool = make_case_pool(size=3, rng=rng)
    for case in pool:
        case.has_entry_score = True

    ems = build_recomputation_emissions(
        case=pool[0], cfg=cfg, rng=rng, force_threshold=True
    )
    current = next(e for e in ems if e.rvt_id == "BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED")
    threshold = next(e for e in ems if e.rvt_id == "BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED")

    assert current.payload["evaluation_id"] == threshold.payload["evaluation_id"]
    assert current.payload["case_id"] == threshold.payload["case_id"]
    assert current.payload["computation_timestamp"] == threshold.payload["computation_timestamp"]
    assert current.payload["trigger"]["event_id"] == threshold.payload["trigger"]["event_id"]
    assert current.payload["trigger"]["kind"] == threshold.payload["trigger"]["kind"]
    # Both events use the same causation_id (= upstream trigger.event_id).
    assert (
        current.payload["envelope"]["causation_id"]
        == threshold.payload["envelope"]["causation_id"]
        == current.payload["trigger"]["event_id"]
    )


def test_no_threshold_implies_no_threshold_event(cfg, rng):
    """When no crossing happens AND probability path doesn't fire, only
    the CURRENT event is emitted."""
    # Force threshold_probability to 0 so the probabilistic branch is silent.
    cfg = type(cfg)(
        **{**cfg.__dict__, "threshold_probability": 0.0}
    )
    pool = make_case_pool(size=3, rng=rng)
    for case in pool:
        case.has_entry_score = True
        case.current_score = 50.0  # mid-band, far from 30/60/80 by ≥10

    # Many iterations; deltas are sampled in [-8, +8] so they cannot
    # cross any threshold from a 50.0 baseline (cases hold state, but
    # we reset score each iteration to stay in the safe band).
    for _ in range(50):
        pool[0].current_score = 50.0
        ems = build_recomputation_emissions(
            case=pool[0], cfg=cfg, rng=rng, force_threshold=False
        )
        rvts = [e.rvt_id for e in ems]
        assert rvts == ["BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED"], rvts


# ---------------------------------------------------------------------------
# Publisher-level atomicity: assert the publish_emissions call ships BOTH
# messages on the same exchange object in a single call, in order CURRENT
# then THRESHOLD. We mock aio-pika entirely — no network.
# ---------------------------------------------------------------------------


@dataclass
class _RecordingExchange:
    """A stand-in for aio_pika.abc.AbstractExchange that records publishes."""

    sent: list[tuple[Any, str]] = field(default_factory=list)

    async def publish(self, message, routing_key: str) -> None:  # noqa: D401
        self.sent.append((message, routing_key))


def test_publisher_ships_pair_in_one_call(validator, cfg, rng):
    pool = make_case_pool(size=2, rng=rng)
    for case in pool:
        case.has_entry_score = True

    ems = build_recomputation_emissions(
        case=pool[0], cfg=cfg, rng=rng, force_threshold=True
    )
    assert len(ems) == 2

    exchange = _RecordingExchange()
    publisher = Publisher(
        connection=MagicMock(),
        channel=MagicMock(),
        exchange=exchange,
        validator=validator,
    )
    asyncio.run(publisher.publish_emissions(ems))

    assert len(exchange.sent) == 2
    keys = [k for (_m, k) in exchange.sent]
    assert keys == [
        "BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED.BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED",
        "BNK.RLVR.EVT.BSP.001.SCORE_THRESHOLD_REACHED.BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED",
    ]
    assert publisher.stats.published == 2
    assert publisher.stats.rejected_by_schema == 0

    # Decode the published bodies and re-validate — defence in depth.
    for msg, _key in exchange.sent:
        body = json.loads(msg.body)
        rvt_id = msg.headers["rvt_id"]
        validator.validate(rvt_id, body)


def test_publisher_refuses_to_publish_invalid_payload(validator, cfg, rng):
    """If validation fails, the message must NOT reach the exchange."""
    pool = make_case_pool(size=1, rng=rng)
    ems = [build_recomputation_emissions(
        case=pool[0], cfg=cfg, rng=rng, force_threshold=True
    )[0]]
    # Corrupt the payload AFTER construction so the validator catches it.
    ems[0].payload["evaluation_type"] = "INVALID_VALUE"

    exchange = _RecordingExchange()
    publisher = Publisher(
        connection=MagicMock(),
        channel=MagicMock(),
        exchange=exchange,
        validator=validator,
    )

    with pytest.raises(Exception):  # noqa: PT011 — ValidationError subclass
        asyncio.run(publisher.publish_emissions(ems))

    assert exchange.sent == []
    assert publisher.stats.published == 0
    assert publisher.stats.rejected_by_schema == 1
