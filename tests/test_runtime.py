"""Tests for ``sme_sidecar_sdk.runtime``."""

from __future__ import annotations

import pytest

from sme_sidecar_sdk import runtime
from sme_sidecar_sdk.config import Settings


def test_configure_returns_state_with_resilience_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SME_SERVICE_NAME", "pedagogico-ms")
    monkeypatch.setenv("SME_ENVIRONMENT", "qa")
    state = runtime.configure()
    try:
        assert state.settings.service_name == "pedagogico-ms"
        assert state.settings.environment == "qa"
        assert state.timeout_enabled is True
        assert state.retry_enabled is True
        assert state.circuit_breaker_enabled is True
        assert state.logging_enabled is True
        assert state.tracing_enabled is False
    finally:
        runtime.shutdown()


def test_configure_disabled_marks_subsystems_off() -> None:
    settings = Settings(SME_SDK_ENABLED=False)
    state = runtime.configure(settings)
    try:
        assert state.settings.enabled is False
        assert state.timeout_enabled is False
        assert state.retry_enabled is False
        assert state.circuit_breaker_enabled is False
        assert state.logging_enabled is False
        assert state.tracing_enabled is False
    finally:
        runtime.shutdown()


def test_state_returns_last_configuration() -> None:
    settings = Settings(
        SME_CIRCUIT_BREAKER_ENABLED=False,
    )
    runtime.configure(settings)
    try:
        snapshot = runtime.state()
        assert snapshot is not None
        assert snapshot.timeout_enabled is True
        assert snapshot.retry_enabled is True
        assert snapshot.circuit_breaker_enabled is False
    finally:
        runtime.shutdown()
