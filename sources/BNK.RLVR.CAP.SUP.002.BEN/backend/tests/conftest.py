"""Shared pytest fixtures — schemas path, validators, etc."""

from __future__ import annotations

from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[1]  # tests → backend


@pytest.fixture(scope="session")
def schemas_dir() -> Path:
    # Package-local vendored snapshot — same dir the service loads at runtime
    # (refresh via `bcm-pack process BNK.RLVR.CAP.SUP.002.BEN`).
    return (
        _BACKEND_ROOT
        / "src"
        / "reliever_beneficiary_anchor"
        / "infrastructure"
        / "schema_validation"
        / "schemas"
    )


@pytest.fixture(scope="session")
def migrations_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "migrations"
