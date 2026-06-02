"""Tests for ``sme_sidecar_sdk.resilience.circuit_breaker``."""

from __future__ import annotations

import pybreaker
import pytest

from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.resilience.circuit_breaker import (
    build_circuit_breaker,
    get_circuit_breaker,
)


def test_get_circuit_breaker_caches_by_name() -> None:
    settings = Settings()
    breaker_a = get_circuit_breaker("turmas-api", settings)
    breaker_b = get_circuit_breaker("turmas-api", settings)
    assert breaker_a is breaker_b


def test_distinct_names_get_distinct_breakers() -> None:
    settings = Settings()
    a = get_circuit_breaker("turmas-api", settings)
    b = get_circuit_breaker("alunos-api", settings)
    assert a is not b


def test_breaker_opens_after_fail_max() -> None:
    settings = Settings(  # type: ignore[call-arg]
        SME_CIRCUIT_BREAKER_FAIL_MAX=2,
        SME_CIRCUIT_BREAKER_RESET_TIMEOUT=60,
    )
    breaker = build_circuit_breaker("flaky", settings)

    def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        breaker.call(fail)

    with pytest.raises(pybreaker.CircuitBreakerError):
        breaker.call(fail)

    with pytest.raises(pybreaker.CircuitBreakerError):
        breaker.call(fail)


def test_disabled_returns_noop_breaker() -> None:
    settings = Settings(SME_CIRCUIT_BREAKER_ENABLED=False)  # type: ignore[call-arg]
    breaker = get_circuit_breaker("disabled", settings)
    assert breaker.call(lambda: 42) == 42

    @breaker
    def fn() -> int:
        return 7

    assert fn() == 7
