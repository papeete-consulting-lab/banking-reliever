"""Pytest plumbing — point the stub at the in-repo fixtures + schemas
regardless of where pytest is launched from.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure the src/ layout is importable when tests run directly without an install.
_STUB_ROOT = Path(__file__).resolve().parent.parent
_SRC = _STUB_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture(autouse=True)
def _isolate_settings_cache(monkeypatch: pytest.MonkeyPatch):
    """Reset the cached settings between tests so env-driven toggles take
    effect immediately.
    """
    # Default the active flags to a known state per test.
    monkeypatch.delenv("RELIEVER_STUB_ACTIVE", raising=False)
    monkeypatch.delenv("RELIEVER_STUB_HTTP_ACTIVE", raising=False)
    from reliever_beneficiary_identity_anchor_stub.settings import reset_settings_cache

    reset_settings_cache()
    yield
    reset_settings_cache()
