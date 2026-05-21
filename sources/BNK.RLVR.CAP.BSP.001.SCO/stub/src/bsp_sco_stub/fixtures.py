"""Synthetic-payload factories.

Owns the three payload shapes (ENTRY_SCORE_COMPUTED,
CURRENT_SCORE_RECOMPUTED, SCORE_THRESHOLD_REACHED) and the case-state
rotation used by the publisher. Threshold detection runs on each
recomputation; when the new score crosses a `TIER_THRESHOLDS` value, an
atomic pair (CURRENT_SCORE_RECOMPUTED + SCORE_THRESHOLD_REACHED) is
emitted — never one without the other (INV.SCO.003).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from . import config
from .envelope import build_envelope, now_iso8601, uuid7_str


@dataclass
class CaseState:
    """Synthetic per-case state — rotates through the case pool."""

    case_id: str
    current_score: float
    tier: str
    has_entry_score: bool = False
    last_evaluation_id: str | None = None


def _initial_tier_for(score: float) -> str:
    """Pick the tier label corresponding to an initial score."""
    tier = "BRONZE"
    for threshold_value, _from, to in config.TIER_THRESHOLDS:
        if score >= threshold_value:
            tier = to
    return tier


def _crossings(
    *, prior: float, after: float
) -> list[tuple[float, str, str, str]]:
    """Return list of crossings between `prior` and `after`.

    Each entry is (threshold_value, tier_from, tier_to, direction). At
    most one crossing per call in this stub (we sample deltas small
    enough to not jump tiers, but the function correctly returns 0..N).
    """
    out: list[tuple[float, str, str, str]] = []
    for tv, tier_from, tier_to in config.TIER_THRESHOLDS:
        if prior < tv <= after:
            out.append((tv, tier_from, tier_to, "UPWARD"))
        elif after < tv <= prior:
            # Crossing downward — note: tier_to/from semantics swap.
            out.append((tv, tier_to, tier_from, "DOWNWARD"))
    return out


def make_case_pool(*, size: int, rng: random.Random) -> list[CaseState]:
    """Build the rotating pool of synthetic cases."""
    lo, hi = config.SCORE_INITIAL_RANGE
    pool: list[CaseState] = []
    for _ in range(size):
        score = round(rng.uniform(lo, hi), 2)
        case = CaseState(
            case_id=uuid7_str(),
            current_score=score,
            tier=_initial_tier_for(score),
        )
        pool.append(case)
    return pool


def _contributing_factors(rng: random.Random) -> list[dict[str, Any]]:
    """Return a small randomised but schema-valid list of factors."""
    n = rng.randint(2, len(config.CONTRIBUTING_FACTORS))
    names = rng.sample(config.CONTRIBUTING_FACTORS, k=n)
    return [
        {
            "name": name,
            "weight": round(rng.uniform(0.0, 1.0), 4),
            "value": round(rng.uniform(-5.0, 5.0), 4),
        }
        for name in names
    ]


@dataclass
class Emission:
    """One bus emission: routing key + RVT id + payload."""

    rvt_id: str
    routing_key: str
    payload: dict[str, Any]


def build_entry_score_event(
    *, case: CaseState, cfg: config.StubConfig, rng: random.Random
) -> Emission:
    """Construct an ENTRY_SCORE_COMPUTED payload (evaluation_type=INITIAL).

    Per the schema:
      - evaluation_type is the literal "INITIAL"
      - envelope.causation_id is the request_id of the CMD.COMPUTE_ENTRY_SCORE
        call (we synthesise one — this stub has no upstream policy)
    """
    evaluation_id = uuid7_str()
    causation_id = uuid7_str()  # synthetic CMD.COMPUTE_ENTRY_SCORE request_id

    case.last_evaluation_id = evaluation_id
    case.has_entry_score = True

    envelope = build_envelope(
        correlation_id=case.case_id,
        causation_id=causation_id,
        schema_version=cfg.schema_version,
    )

    payload: dict[str, Any] = {
        "envelope": envelope,
        "case_id": case.case_id,
        "evaluation_id": evaluation_id,
        "score_value": case.current_score,
        "model_version": cfg.model_version,
        "evaluation_type": "INITIAL",
        "computation_timestamp": now_iso8601(),
        "contributing_factors": _contributing_factors(rng),
    }
    return Emission(
        rvt_id="BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED",
        routing_key=config.ROUTING_KEY_ENTRY,
        payload=payload,
    )


def _build_trigger(rng: random.Random, *, with_event_id: str | None = None) -> dict[str, Any]:
    kind = rng.choice(config.TRIGGER_KINDS)
    polarity = "negative" if kind in {"TRANSACTION_REFUSED", "RELAPSE_SIGNAL"} else "positive"
    trigger: dict[str, Any] = {
        "kind": kind,
        "event_id": with_event_id or uuid7_str(),
        "polarity": polarity,
    }
    if kind.startswith("TRANSACTION_"):
        trigger["amount"] = round(rng.uniform(5.0, 500.0), 2)
        trigger["category"] = rng.choice(
            ["GROCERIES", "TRANSPORT", "RENT", "ENERGY", "MISC"]
        )
    elif kind.endswith("_SIGNAL"):
        trigger["impact_score"] = round(rng.uniform(-3.0, 3.0), 3)
    return trigger


def build_recomputation_emissions(
    *,
    case: CaseState,
    cfg: config.StubConfig,
    rng: random.Random,
    force_threshold: bool = False,
) -> list[Emission]:
    """Build a CURRENT_SCORE_RECOMPUTED emission plus, atomically, a
    SCORE_THRESHOLD_REACHED emission iff a threshold was crossed.

    INV.SCO.003 — the two events SHARE the same evaluation_id and the
    same trigger.event_id. The threshold event also reuses the CURRENT
    event's case_id and computation_timestamp.

    Parameters
    ----------
    force_threshold:
        If True, pick a delta large enough to guarantee a tier crossing
        (used by tests). Otherwise, sample a small delta and emit a
        threshold event only if a crossing genuinely occurred OR with
        probability `cfg.threshold_probability`.
    """
    evaluation_id = uuid7_str()
    trigger = _build_trigger(rng)
    causation_id = trigger["event_id"]  # upstream RVT's event_id per schema

    prior_score = case.current_score

    if force_threshold:
        # Pick the nearest crossable threshold; nudge across it.
        target = _pick_crossable_threshold(prior_score, rng=rng)
        new_score = round(target + (rng.uniform(0.5, 3.0) if target >= prior_score else -rng.uniform(0.5, 3.0)), 2)
        # Adjust polarity for coherence.
        trigger["polarity"] = "positive" if new_score >= prior_score else "negative"
    else:
        # Small random delta in [-8, +8].
        delta = round(rng.uniform(-8.0, 8.0), 2)
        new_score = round(prior_score + delta, 2)

    new_score = max(0.0, min(100.0, new_score))
    delta_score = round(new_score - prior_score, 2)

    case.current_score = new_score
    case.last_evaluation_id = evaluation_id

    computation_ts = now_iso8601()
    contributing = _contributing_factors(rng)

    current_envelope = build_envelope(
        correlation_id=case.case_id,
        causation_id=causation_id,
        schema_version=cfg.schema_version,
    )
    current_payload: dict[str, Any] = {
        "envelope": current_envelope,
        "case_id": case.case_id,
        "evaluation_id": evaluation_id,
        "score_value": new_score,
        "delta_score": delta_score,
        "model_version": cfg.model_version,
        "evaluation_type": "CURRENT",
        "computation_timestamp": computation_ts,
        "trigger": trigger,
        "contributing_factors": contributing,
    }

    emissions: list[Emission] = [
        Emission(
            rvt_id="BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED",
            routing_key=config.ROUTING_KEY_CURRENT,
            payload=current_payload,
        )
    ]

    crossings = _crossings(prior=prior_score, after=new_score)
    must_emit_threshold = bool(crossings) or force_threshold

    # Probabilistic injection: only when NO genuine crossing happened
    # AND not forced. We synthesise a crossing of the nearest threshold
    # so the event is meaningful.
    if not must_emit_threshold and rng.random() < cfg.threshold_probability:
        nearest = _nearest_threshold(prior_score)
        direction = "UPWARD" if new_score >= prior_score else "DOWNWARD"
        if direction == "UPWARD":
            tier_from, tier_to = nearest[1], nearest[2]
        else:
            tier_from, tier_to = nearest[2], nearest[1]
        crossings = [(nearest[0], tier_from, tier_to, direction)]
        must_emit_threshold = True

    if must_emit_threshold:
        if not crossings:
            # force_threshold=True but the score landed on the boundary
            # by coincidence; synthesise from nearest.
            nearest = _nearest_threshold(prior_score)
            direction = "UPWARD" if new_score >= prior_score else "DOWNWARD"
            if direction == "UPWARD":
                tier_from, tier_to = nearest[1], nearest[2]
            else:
                tier_from, tier_to = nearest[2], nearest[1]
            crossings = [(nearest[0], tier_from, tier_to, direction)]

        # Use the first crossing (in this stub there's at most one anyway).
        tv, tier_from, tier_to, direction = crossings[0]
        case.tier = tier_to if direction == "UPWARD" else tier_from

        threshold_envelope = build_envelope(
            correlation_id=case.case_id,
            causation_id=causation_id,
            schema_version=cfg.schema_version,
        )
        threshold_payload: dict[str, Any] = {
            "envelope": threshold_envelope,
            "case_id": case.case_id,
            "evaluation_id": evaluation_id,            # same as CURRENT → proves atomicity
            "score_value": new_score,
            "delta_score": delta_score,
            "model_version": cfg.model_version,
            "computation_timestamp": computation_ts,
            "threshold": {
                "value": tv,
                "tier_from": tier_from,
                "tier_to": tier_to,
            },
            "direction": direction,
            "trigger": {
                "kind": trigger["kind"],
                "event_id": trigger["event_id"],       # same trigger.event_id as CURRENT
            },
        }
        emissions.append(
            Emission(
                rvt_id="BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED",
                routing_key=config.ROUTING_KEY_THRESHOLD,
                payload=threshold_payload,
            )
        )

    return emissions


def _nearest_threshold(score: float) -> tuple[float, str, str]:
    """Return the threshold triple closest to `score`."""
    return min(config.TIER_THRESHOLDS, key=lambda t: abs(t[0] - score))


def _pick_crossable_threshold(score: float, *, rng: random.Random) -> float:
    """Pick a threshold value the score is not currently exactly on."""
    candidates = [t[0] for t in config.TIER_THRESHOLDS if abs(t[0] - score) > 0.01]
    if not candidates:
        # Fall back — should never happen with reasonable initial range.
        return config.TIER_THRESHOLDS[0][0]
    return rng.choice(candidates)


def next_emissions(
    *,
    pool: list[CaseState],
    cfg: config.StubConfig,
    rng: random.Random,
) -> list[Emission]:
    """Pick a case and produce its next emission batch.

    The first time a case is picked, ENTRY_SCORE_COMPUTED is emitted
    (one-shot baseline per BNK.RLVR.OBJ.BSP.001.EVALUATION). Subsequent picks
    emit CURRENT_SCORE_RECOMPUTED, possibly paired with
    SCORE_THRESHOLD_REACHED.

    `cfg.entry_score_ratio` only matters during steady state — if all
    cases have already had their entry score, it is ignored.
    """
    case = rng.choice(pool)

    if not case.has_entry_score:
        return [build_entry_score_event(case=case, cfg=cfg, rng=rng)]

    # Once entry exists, occasionally still emit an entry for a *fresh*
    # case if the pool has any (otherwise pure recomputation flow).
    fresh_cases = [c for c in pool if not c.has_entry_score]
    if fresh_cases and rng.random() < cfg.entry_score_ratio:
        return [build_entry_score_event(case=rng.choice(fresh_cases), cfg=cfg, rng=rng)]

    return build_recomputation_emissions(case=case, cfg=cfg, rng=rng)
