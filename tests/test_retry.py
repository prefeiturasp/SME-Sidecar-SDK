"""Tests for ``sme_sidecar_sdk.resilience.retry``."""

from __future__ import annotations

import pytest

from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.resilience.retry import retry_policy


def test_retries_until_success() -> None:
    settings = Settings(
        SME_RETRY_ATTEMPTS=3,
        SME_RETRY_BACKOFF_MIN=0,
        SME_RETRY_BACKOFF_MAX=0,
    )
    calls = {"count": 0}

    @retry_policy(settings=settings, exceptions=(ConnectionError,))
    def flaky() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise ConnectionError("boom")
        return "ok"

    assert flaky() == "ok"
    assert calls["count"] == 3


def test_reraises_original_exception_after_max_attempts() -> None:
    settings = Settings(
        SME_RETRY_ATTEMPTS=2,
        SME_RETRY_BACKOFF_MIN=0,
        SME_RETRY_BACKOFF_MAX=0,
    )
    calls = {"count": 0}

    @retry_policy(settings=settings, exceptions=(ConnectionError,))
    def always_fail() -> None:
        calls["count"] += 1
        raise ConnectionError("nope")

    with pytest.raises(ConnectionError):
        always_fail()
    assert calls["count"] == 2


def test_does_not_retry_unmatched_exception() -> None:
    settings = Settings(
        SME_RETRY_ATTEMPTS=3,
        SME_RETRY_BACKOFF_MIN=0,
        SME_RETRY_BACKOFF_MAX=0,
    )
    calls = {"count": 0}

    @retry_policy(settings=settings, exceptions=(ConnectionError,))
    def boom() -> None:
        calls["count"] += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        boom()
    assert calls["count"] == 1


def test_disabled_retry_returns_function_unchanged() -> None:
    settings = Settings(SME_RETRY_ENABLED=False)

    @retry_policy(settings=settings)
    def fn() -> str:
        return "value"

    assert fn() == "value"
