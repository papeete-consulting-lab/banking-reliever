"""Runtime configuration for the BNK.RLVR.CAP.BSP.001.SCO stub.

All knobs are env-driven. Defaults preserve the contract behaviour stated
in TASK-002 Definition of Done:
  - cadence default 1–10 events / minute combined
  - threshold probability default 1 / 10
  - master switch STUB_ACTIVE (default false — inactive in production)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# Routing keys mandated by process/BNK.RLVR.CAP.BSP.001.SCO/bus.yaml.
EXCHANGE_NAME = "bsp.001.sco-events"
ROUTING_KEY_ENTRY = (
    "BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED.BNK.RLVR.RVT.BSP.001.ENTRY_SCORE_COMPUTED"
)
ROUTING_KEY_CURRENT = (
    "BNK.RLVR.EVT.BSP.001.SCORE_RECOMPUTED.BNK.RLVR.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED"
)
ROUTING_KEY_THRESHOLD = (
    "BNK.RLVR.EVT.BSP.001.SCORE_THRESHOLD_REACHED.BNK.RLVR.RVT.BSP.001.SCORE_THRESHOLD_REACHED"
)

EMITTING_CAPABILITY = "BNK.RLVR.CAP.BSP.001.SCO"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover — defensive
        raise ValueError(f"env {name} must be an integer, got {raw!r}") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:  # pragma: no cover — defensive
        raise ValueError(f"env {name} must be a float, got {raw!r}") from exc


def _default_schemas_dir() -> Path:
    """Locate the package-local *vendored* schema snapshot.

    The RVT.*/CMD.* JSON Schemas are vendored as a static snapshot under
    ``bsp_sco_stub/schemas/`` (a stub owns the contract snapshot it validates
    against). They live next to this module, so resolution is simply
    ``Path(__file__).parent / "schemas"`` — no repo-root / process/ lookup.
    Refresh the snapshot via ``rlv-knowledge process BNK.RLVR.CAP.BSP.001.SCO``
    (``.schemas["<FILE>.schema.json"]``).
    Overridable via env STUB_SCHEMAS_DIR for CI / docker scenarios.
    """
    raw = os.environ.get("STUB_SCHEMAS_DIR")
    if raw:
        return Path(raw).resolve()
    return (Path(__file__).resolve().parent / "schemas").resolve()


@dataclass(frozen=True)
class StubConfig:
    """All runtime settings as an immutable record."""

    active: bool
    cadence_per_minute: float          # combined RVT.ENTRY + RVT.CURRENT cadence
    threshold_probability: float       # P(threshold crossing | recomputation)
    entry_score_ratio: float           # fraction of recomputations published as ENTRY (one-shot baseline)
    rabbitmq_url: str
    exchange_name: str
    schemas_dir: Path
    model_version: str
    schema_version: str
    case_pool_size: int                # number of synthetic case_ids to rotate

    @classmethod
    def from_env(cls) -> "StubConfig":
        active = _env_bool("STUB_ACTIVE", False)
        cadence = _env_float("STUB_CADENCE_PER_MIN", 6.0)
        threshold_p = _env_float("STUB_THRESHOLD_PROBABILITY", 0.1)
        entry_ratio = _env_float("STUB_ENTRY_RATIO", 0.1)
        rabbitmq_url = os.environ.get(
            "RABBITMQ_URL", "amqp://guest:guest@localhost:47656/"
        )
        exchange = os.environ.get("STUB_EXCHANGE_NAME", EXCHANGE_NAME)
        schemas_dir = _default_schemas_dir()
        model_version = os.environ.get("STUB_MODEL_VERSION", "0.2.0")
        schema_version = os.environ.get("STUB_SCHEMA_VERSION", "0.2.0")
        case_pool = max(1, _env_int("STUB_CASE_POOL_SIZE", 8))

        if cadence < 1 or cadence > 10:
            if not _env_bool("STUB_CADENCE_OUT_OF_RANGE", False):
                raise ValueError(
                    "STUB_CADENCE_PER_MIN must be in [1, 10] "
                    "(set STUB_CADENCE_OUT_OF_RANGE=true to override; "
                    f"got {cadence})"
                )
        if not (0.0 <= threshold_p <= 1.0):
            raise ValueError(
                "STUB_THRESHOLD_PROBABILITY must be in [0, 1] "
                f"(got {threshold_p})"
            )
        if not (0.0 <= entry_ratio <= 1.0):
            raise ValueError(
                f"STUB_ENTRY_RATIO must be in [0, 1] (got {entry_ratio})"
            )

        return cls(
            active=active,
            cadence_per_minute=cadence,
            threshold_probability=threshold_p,
            entry_score_ratio=entry_ratio,
            rabbitmq_url=rabbitmq_url,
            exchange_name=exchange,
            schemas_dir=schemas_dir,
            model_version=model_version,
            schema_version=schema_version,
            case_pool_size=case_pool,
        )


# Synthetic tier thresholds — assumption documented in README/TASK-002 plan.
# BNK.RLVR.CAP.BSP.001.TIE owns the real configuration; this stub fixes a tiny table
# so threshold detection is deterministic enough to test.
TIER_THRESHOLDS: tuple[tuple[float, str, str], ...] = (
    (30.0, "BRONZE", "SILVER"),
    (60.0, "SILVER", "GOLD"),
    (80.0, "GOLD", "PLATINUM"),
)


# Initial behavioural score per synthetic case, sampled uniformly in [40, 70].
SCORE_INITIAL_RANGE: tuple[float, float] = (40.0, 70.0)


# Contributing-factor catalogue — schema only constrains shape, not enum.
CONTRIBUTING_FACTORS: tuple[str, ...] = (
    "transaction_amount",
    "transaction_recurrence",
    "repayment_ratio",
    "savings_growth",
    "incident_count",
    "category_diversity",
)


# Trigger discriminator enum (mirrors the schemas verbatim).
TRIGGER_KINDS: tuple[str, ...] = (
    "TRANSACTION_AUTHORIZED",
    "TRANSACTION_REFUSED",
    "RELAPSE_SIGNAL",
    "PROGRESSION_SIGNAL",
)
