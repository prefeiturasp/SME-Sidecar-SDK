"""Tests for ``sme_sidecar_sdk.config``."""

from __future__ import annotations

import pytest

from sme_sidecar_sdk.config import Settings, get_settings, reset_settings_cache


def test_defaults_when_no_env_vars() -> None:
    settings = Settings()
    assert settings.enabled is True
    assert settings.service_name == "unnamed-service"
    assert settings.environment == "dev"
    assert settings.timeout_seconds == pytest.approx(10.0)
    assert settings.retry_attempts == 3
    assert settings.circuit_breaker_fail_max == 5
    assert settings.logging_enabled is True
    assert settings.log_level == "ERROR"
    assert settings.log_format == "json"
    assert settings.broker == "rabbitmq"
    assert settings.log_queue == ""
    assert settings.log_queue_buffer_size == 10_000
    assert settings.correlation_id_header == "X-Request-ID"
    assert settings.observability_backend == "elastic"
    assert settings.otel_enabled is False


def test_env_vars_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SME_SERVICE_NAME", "pedagogico-ms")
    monkeypatch.setenv("SME_ENVIRONMENT", "qa")
    monkeypatch.setenv("SME_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("SME_RETRY_ATTEMPTS", "5")
    monkeypatch.setenv("SME_CIRCUIT_BREAKER_FAIL_MAX", "10")
    monkeypatch.setenv("SME_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SME_OTEL_ENABLED", "true")

    settings = Settings()

    assert settings.service_name == "pedagogico-ms"
    assert settings.environment == "qa"
    assert settings.timeout_seconds == pytest.approx(7.5)
    assert settings.retry_attempts == 5
    assert settings.circuit_breaker_fail_max == 10
    assert settings.log_level == "DEBUG"
    assert settings.otel_enabled is True


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SME_SERVICE_NAME", "first")
    first = get_settings()
    monkeypatch.setenv("SME_SERVICE_NAME", "second")
    cached = get_settings()
    assert cached is first
    reset_settings_cache()
    refreshed = get_settings()
    assert refreshed.service_name == "second"


def test_invalid_timeout_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SME_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValueError):
        Settings()


def test_invalid_broker_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SME_BROKER", "redis")
    with pytest.raises(ValueError):
        Settings()


def test_invalid_observability_backend_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SME_OBSERVABILITY_BACKEND", "jaeger")
    with pytest.raises(ValueError):
        Settings()
