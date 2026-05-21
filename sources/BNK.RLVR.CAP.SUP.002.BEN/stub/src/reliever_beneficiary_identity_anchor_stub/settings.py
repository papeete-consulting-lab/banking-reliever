"""Stub settings — env + config/stub.toml via pydantic-settings.

All env vars are prefixed ``RELIEVER_``. The stub.toml file is loaded
once at startup as the source of defaults; env vars override.
"""
from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Repository root candidates — the stub package is at:
#   sources/BNK.RLVR.CAP.SUP.002.BEN/stub/src/reliever_beneficiary_identity_anchor_stub/settings.py
# So:
#   __file__ → .../src/reliever_beneficiary_identity_anchor_stub/settings.py
#   parents[1] = src/, parents[2] = stub/, parents[5] = repo root
_PKG_DIR = Path(__file__).resolve().parent
_STUB_ROOT = _PKG_DIR.parent.parent  # sources/BNK.RLVR.CAP.SUP.002.BEN/stub/
_REPO_ROOT = _STUB_ROOT.parent.parent.parent  # repo root


def _load_toml_defaults() -> dict:
    """Load stub.toml — returns empty dict if missing (tests don't require it)."""
    cfg_path = _STUB_ROOT / "config" / "stub.toml"
    if not cfg_path.is_file():
        return {}
    with cfg_path.open("rb") as fh:
        return tomllib.load(fh)


_TOML = _load_toml_defaults()


def _toml(*path: str, default=None):
    node = _TOML
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


class StubSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RELIEVER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── identity
    capability_id: str = Field(default=_toml("service", "capability_id", default="BNK.RLVR.CAP.SUP.002.BEN"))
    capability_zone: str = Field(default=_toml("service", "capability_zone", default="SUPPORT"))
    service_name: str = Field(
        default=_toml("service", "name", default="reliever-beneficiary-identity-anchor-stub")
    )

    # ── http
    http_host: str = Field(default=_toml("http", "host", default="0.0.0.0"))
    http_port: int = Field(default=_toml("http", "port", default=54679))

    # ── bus
    amqp_url: str = Field(
        default=_toml("bus", "amqp_url", default="amqp://admin:password@localhost:54879/")
    )
    bus_exchange: str = Field(default=_toml("bus", "exchange", default="sup.002.ben-events"))
    bus_resource_event: str = Field(
        default=_toml("bus", "resource_event", default="BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED")
    )
    bus_business_event: str = Field(
        default=_toml("bus", "business_event", default="BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED")
    )
    bus_routing_key: str = Field(
        default=_toml(
            "bus",
            "routing_key",
            default="BNK.RLVR.EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED",
        )
    )

    # ── cadence (events / minute)
    cadence_min_per_minute: int = Field(
        default=_toml("cadence", "min_per_minute", default=1)
    )
    cadence_max_per_minute: int = Field(
        default=_toml("cadence", "max_per_minute", default=10)
    )

    # ── stub master toggles
    stub_active: bool = Field(default=_toml("stub", "active", default=False))
    stub_http_active: bool = Field(default=_toml("stub", "http_active", default=True))

    # ── filesystem anchors (computed; never set via env)
    repo_root: Path = _REPO_ROOT
    stub_root: Path = _STUB_ROOT

    @property
    def schemas_dir(self) -> Path:
        # Package-local *vendored* schema snapshot (a stub owns the contract
        # snapshot it validates against). Refresh via
        # `bcm-pack process BNK.RLVR.CAP.SUP.002.BEN` (`.schemas["<FILE>.schema.json"]`).
        return _PKG_DIR / "schemas"

    @property
    def fixtures_dir(self) -> Path:
        return self.stub_root / "fixtures"

    @property
    def rvt_schema_path(self) -> Path:
        return self.schemas_dir / "BNK.RLVR.RVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED.schema.json"


@lru_cache(maxsize=1)
def get_settings() -> StubSettings:
    return StubSettings()


def reset_settings_cache() -> None:
    """Test helper — clears the lru_cache so env mutations are picked up."""
    get_settings.cache_clear()
