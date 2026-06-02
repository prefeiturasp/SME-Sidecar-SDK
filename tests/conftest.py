"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from sme_sidecar_sdk import config as config_module
from sme_sidecar_sdk.resilience import circuit_breaker as cb_module


@pytest.fixture(autouse=True)
def _reset_sdk_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reset cached SDK state and SME_* env vars between tests."""
    sme_keys = [key for key in os.environ if key.startswith("SME_")]
    for key in sme_keys:
        monkeypatch.delenv(key, raising=False)

    config_module.reset_settings_cache()
    cb_module.reset_registry()

    yield

    config_module.reset_settings_cache()
    cb_module.reset_registry()
