"""Tests for ``sme_sidecar_sdk.resilience.timeout``."""

from __future__ import annotations

import httpx
import pytest

from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.observability.context import correlation_context
from sme_sidecar_sdk.resilience.timeout import (
    build_async_client,
    build_sync_client,
    build_timeout,
)


def test_build_timeout_uses_setting() -> None:
    settings = Settings(SME_TIMEOUT_SECONDS=7.5)
    timeout = build_timeout(settings)
    assert timeout.read == pytest.approx(7.5)


def test_build_timeout_disabled() -> None:
    settings = Settings(SME_TIMEOUT_ENABLED=False)
    timeout = build_timeout(settings)
    assert timeout.read is None


def test_sync_client_applies_timeout() -> None:
    settings = Settings(SME_TIMEOUT_SECONDS=3.0)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    with build_sync_client(settings, transport=transport) as client:
        response = client.get("http://example.test/")
        assert client.timeout.read == pytest.approx(3.0)
        assert response.status_code == 200


def test_sync_client_propagates_request_id_and_preserves_hooks() -> None:
    seen: dict[str, str] = {}

    def custom_hook(request: httpx.Request) -> None:
        seen["custom"] = request.url.path

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request_id"] = request.headers["X-Request-ID"]
        return httpx.Response(200)

    with (
        correlation_context(correlation_id="request-123"),
        build_sync_client(
            transport=httpx.MockTransport(handler),
            event_hooks={"request": [custom_hook]},
        ) as client,
    ):
        client.get("http://example.test/recurso")

    assert seen == {
        "custom": "/recurso",
        "request_id": "request-123",
    }


def test_reserved_kwargs_rejected() -> None:
    with pytest.raises(ValueError):
        build_sync_client(timeout=1)
    with pytest.raises(ValueError):
        build_async_client(timeout=1)


@pytest.mark.asyncio
async def test_async_client_applies_timeout() -> None:
    settings = Settings(SME_TIMEOUT_SECONDS=4.0)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with build_async_client(settings, transport=transport) as client:
        response = await client.get("http://example.test/")
        assert client.timeout.read == pytest.approx(4.0)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_async_client_propagates_request_id() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request_id"] = request.headers["X-Request-ID"]
        return httpx.Response(200)

    with correlation_context(correlation_id="async-123"):
        async with build_async_client(
            transport=httpx.MockTransport(handler),
        ) as client:
            await client.get("http://example.test/")

    assert seen["request_id"] == "async-123"
