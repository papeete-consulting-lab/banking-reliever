"""Shared pytest fixtures — schemas path, validators, etc."""

from __future__ import annotations

from pathlib import Path

import pytest

# Repo root  =  tests/../../../../../   (tests → backend → BNK.RLVR.CAP.SUP.002.BEN → sources → repo)
_REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="session")
def schemas_dir() -> Path:
    return _REPO_ROOT / "process" / "BNK.RLVR.CAP.SUP.002.BEN" / "schemas"


@pytest.fixture(scope="session")
def migrations_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "migrations"
