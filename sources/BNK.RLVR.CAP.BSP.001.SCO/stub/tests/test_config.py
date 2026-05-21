"""Configuration loader — env-var parsing + validation."""
from __future__ import annotations

import os
import re

import pytest

from bsp_sco_stub.config import StubConfig


SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Each test starts from a clean STUB_* slate."""
    for key in list(os.environ):
        if key.startswith("STUB_") or key == "RABBITMQ_URL":
            monkeypatch.delenv(key, raising=False)
    yield


def test_defaults_are_safe(monkeypatch):
    cfg = StubConfig.from_env()
    assert cfg.active is False, "STUB_ACTIVE must default to false (inactive in production)"
    assert 1.0 <= cfg.cadence_per_minute <= 10.0
    assert 0.0 <= cfg.threshold_probability <= 1.0
    assert cfg.exchange_name == "bsp.001.sco-events"
    assert SEMVER.match(cfg.model_version), cfg.model_version
    assert SEMVER.match(cfg.schema_version), cfg.schema_version


def test_active_flag_parses_truthy(monkeypatch):
    monkeypatch.setenv("STUB_ACTIVE", "true")
    assert StubConfig.from_env().active is True
    monkeypatch.setenv("STUB_ACTIVE", "false")
    assert StubConfig.from_env().active is False
    monkeypatch.setenv("STUB_ACTIVE", "1")
    assert StubConfig.from_env().active is True


def test_cadence_out_of_range_is_rejected(monkeypatch):
    monkeypatch.setenv("STUB_CADENCE_PER_MIN", "100")
    with pytest.raises(ValueError, match="STUB_CADENCE_PER_MIN"):
        StubConfig.from_env()


def test_cadence_override_allows_out_of_range(monkeypatch):
    monkeypatch.setenv("STUB_CADENCE_PER_MIN", "100")
    monkeypatch.setenv("STUB_CADENCE_OUT_OF_RANGE", "true")
    cfg = StubConfig.from_env()
    assert cfg.cadence_per_minute == 100.0


def test_threshold_probability_out_of_range_is_rejected(monkeypatch):
    monkeypatch.setenv("STUB_THRESHOLD_PROBABILITY", "1.5")
    with pytest.raises(ValueError, match="STUB_THRESHOLD_PROBABILITY"):
        StubConfig.from_env()
