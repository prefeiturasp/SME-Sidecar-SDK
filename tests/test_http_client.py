"""Tests for ``sme_sidecar_sdk.http``."""

from __future__ import annotations

import httpx
import pybreaker
import pytest

from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.http import (
    build_async_http_client,
    build_http_client,
)
from sme_sidecar_sdk.http import client as http_client_module
from sme_sidecar_sdk.observability.context import correlation_context


class FakeLogger:
    """Logger de teste que guarda eventos estruturados."""

    def __init__(self) -> None:
        """Inicializa a lista de eventos capturados."""
        self.events: list[tuple[str, str, dict[str, object]]] = []

    def info(self, event: str, **kwargs: object) -> None:
        """Guarda um evento de info."""
        self.events.append(("info", event, kwargs))

    def error(self, event: str, **kwargs: object) -> None:
        """Guarda um evento de erro."""
        self.events.append(("error", event, kwargs))


def test_http_client_sends_request_and_logs_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = FakeLogger()

    def get_logger(_: str | None = None) -> FakeLogger:
        return logger

    monkeypatch.setattr(http_client_module, "get_logger", get_logger)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, request=request)

    with build_http_client(
        "pedagogico-ms",
        base_url="http://pedagogico.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.get("/componentes")

    assert response.json() == {"ok": True}
    assert logger.events[0][0] == "info"
    assert logger.events[0][1] == "http_client_request_completed"
    assert logger.events[0][2]["upstream"] == "pedagogico-ms"
    assert logger.events[0][2]["http_path"] == "/componentes"


def test_http_client_propagates_request_id_and_preserves_hooks() -> None:
    seen: dict[str, str] = {}

    def custom_hook(request: httpx.Request) -> None:
        seen["custom"] = request.url.path

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request_id"] = request.headers["X-Request-ID"]
        return httpx.Response(200, request=request)

    with (
        correlation_context(correlation_id="request-123"),
        build_http_client(
            "pedagogico-ms",
            transport=httpx.MockTransport(handler),
            event_hooks={"request": [custom_hook]},
        ) as client,
    ):
        client.get("http://pedagogico.test/componentes")

    assert seen["request_id"] == "request-123"
    assert seen["custom"] == "/componentes"


def test_http_client_injects_trace_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def inject_trace_context(headers: httpx.Headers) -> None:
        headers["traceparent"] = "00-" + ("1" * 32) + "-" + ("2" * 16) + "-01"

    monkeypatch.setattr(
        http_client_module,
        "inject_trace_context",
        inject_trace_context,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        seen["traceparent"] = request.headers["traceparent"]
        return httpx.Response(200, request=request)

    with build_http_client(
        "pedagogico-ms",
        transport=httpx.MockTransport(handler),
    ) as client:
        client.get("http://pedagogico.test/componentes")

    assert seen["traceparent"] == (
        "00-" + ("1" * 32) + "-" + ("2" * 16) + "-01"
    )


def test_http_client_retries_transport_errors() -> None:
    settings = Settings(
        SME_RETRY_ATTEMPTS=2,
        SME_RETRY_BACKOFF_MIN=0,
        SME_RETRY_BACKOFF_MAX=0,
    )
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, request=request)

    with build_http_client(
        "retry-ms",
        settings=settings,
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.get("http://retry.test/recurso")

    assert response.status_code == 200
    assert calls["count"] == 2


def test_http_client_raises_for_status_and_logs_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = FakeLogger()

    def get_logger(_: str | None = None) -> FakeLogger:
        return logger

    monkeypatch.setattr(http_client_module, "get_logger", get_logger)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    with (
        build_http_client(
            "erro-ms",
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        client.get("http://erro.test/falha")

    assert logger.events[0][0] == "error"
    assert logger.events[0][1] == "http_client_request_failed"
    assert logger.events[0][2]["http_status_code"] == 500
    assert logger.events[0][2]["http_path"] == "/falha"


def test_http_client_uses_circuit_breaker() -> None:
    settings = Settings(
        SME_RETRY_ENABLED=False,
        SME_CIRCUIT_BREAKER_FAIL_MAX=2,
        SME_CIRCUIT_BREAKER_RESET_TIMEOUT=60,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    with build_http_client(
        "breaker-ms",
        settings=settings,
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            client.get("http://breaker.test/falha")
        with pytest.raises(pybreaker.CircuitBreakerError):
            client.get("http://breaker.test/falha")


@pytest.mark.asyncio
async def test_async_http_client_sends_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, request=request)

    async with build_async_http_client(
        "pedagogico-ms",
        base_url="http://pedagogico.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        response = await client.get("/componentes")

    assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_async_http_client_propagates_request_id() -> None:
    seen: dict[str, str] = {}

    async def custom_hook(request: httpx.Request) -> None:
        seen["custom"] = request.url.path

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request_id"] = request.headers["X-Request-ID"]
        return httpx.Response(200, request=request)

    with correlation_context(correlation_id="async-request-123"):
        async with build_async_http_client(
            "pedagogico-ms",
            transport=httpx.MockTransport(handler),
            event_hooks={"request": [custom_hook]},
        ) as client:
            await client.get("http://pedagogico.test/componentes")

    assert seen["request_id"] == "async-request-123"
    assert seen["custom"] == "/componentes"


@pytest.mark.asyncio
async def test_async_http_client_retries_transport_errors() -> None:
    settings = Settings(
        SME_RETRY_ATTEMPTS=2,
        SME_RETRY_BACKOFF_MIN=0,
        SME_RETRY_BACKOFF_MAX=0,
    )
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, request=request)

    async with build_async_http_client(
        "async-retry-ms",
        settings=settings,
        transport=httpx.MockTransport(handler),
    ) as client:
        response = await client.get("http://async-retry.test/recurso")

    assert response.status_code == 200
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_async_http_client_uses_circuit_breaker() -> None:
    settings = Settings(
        SME_RETRY_ENABLED=False,
        SME_CIRCUIT_BREAKER_FAIL_MAX=2,
        SME_CIRCUIT_BREAKER_RESET_TIMEOUT=60,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    async with build_async_http_client(
        "async-breaker-ms",
        settings=settings,
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.get("http://async-breaker.test/falha")
        with pytest.raises(pybreaker.CircuitBreakerError):
            await client.get("http://async-breaker.test/falha")
