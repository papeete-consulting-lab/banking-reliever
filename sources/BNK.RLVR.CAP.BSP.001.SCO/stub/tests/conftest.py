"""Shared fixtures for the bsp-sco-stub test suite.

All tests run OFFLINE — no RabbitMQ connection, no network. The
publisher's validation path is exercised directly; the AMQP path is
mocked when needed.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

# Ensure the in-tree src/ is importable without an install step.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Canonical schemas live in process/BNK.RLVR.CAP.BSP.001.SCO/schemas/ — four
# directories up from this test file.
SCHEMAS_DIR = ROOT.parents[2] / "process" / "BNK.RLVR.CAP.BSP.001.SCO" / "schemas"


from bsp_sco_stub.config import StubConfig  # noqa: E402
from bsp_sco_stub.schema_validator import SchemaValidator  # noqa: E402


@pytest.fixture(scope="session")
def schemas_dir() -> Path:
    assert SCHEMAS_DIR.is_dir(), (
        f"Canonical schemas dir missing: {SCHEMAS_DIR}. "
        "Tests must read RVT.*.schema.json from process/BNK.RLVR.CAP.BSP.001.SCO/schemas/."
    )
    return SCHEMAS_DIR


@pytest.fixture(scope="session")
def validator(schemas_dir: Path) -> SchemaValidator:
    return SchemaValidator(schemas_dir)


@pytest.fixture()
def cfg(schemas_dir: Path) -> StubConfig:
    """A deterministic-friendly config that does NOT touch the env."""
    return StubConfig(
        active=True,
        cadence_per_minute=6.0,
        threshold_probability=0.1,
        entry_score_ratio=0.0,
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        exchange_name="bsp.001.sco-events",
        schemas_dir=schemas_dir,
        model_version="0.0.1",
        schema_version="0.2.0",
        case_pool_size=4,
    )


@pytest.fixture()
def rng() -> random.Random:
    return random.Random(20260515)
