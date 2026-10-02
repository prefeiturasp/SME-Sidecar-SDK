from __future__ import annotations

import sys
from types import ModuleType
from typing import Any, cast

import pytest

from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.integrations.asgi import (
    ASGIApp,
    ASGIObservabilityMiddleware,
    Message,
    Receive,
    Scope,
    Send,
    instrument_asgi_application,
)
from sme_sidecar_sdk.observability.context import get_correlation_id


async def _receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


@pytest.mark.asyncio
async def test_asgi_middleware_reuses_request_id_and_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_request_ids: list[str | None] = []
    sent_messages: list[Message] = []

    async def app(
        scope: Scope,
        _receive: Receive,
        send: Send,
    ) -> None:
        seen_request_ids.append(get_correlation_id())
        assert scope["request_id"] == "request-123"
        await send(
            {
                "type": "http.response.start",
                "status": 204,
                "headers": [],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    async def send(message: Message) -> None:
        sent_messages.append(message)

    info_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "sme_sidecar_sdk.integrations.asgi.log.info",
        lambda _event, **kwargs: info_calls.append(kwargs),
    )

    middleware = ASGIObservabilityMiddleware(app)
    await middleware(
        {
            "type": "http",
            "method": "GET",
            "path": "/health/",
            "headers": [(b"x-request-id", b"request-123")],
        },
        _receive,
        send,
    )

    assert seen_request_ids == ["request-123"]
    assert get_correlation_id() is None
    assert sent_messages[0]["headers"] == [(b"x-request-id", b"request-123")]
    assert info_calls[0]["http_status_code"] == 204
    assert info_calls[0]["http_path"] == "/health/"


@pytest.mark.asyncio
async def test_asgi_middleware_passes_non_http_scope() -> None:
    called = False

    async def app(
        scope: Scope,
        _receive: Receive,
        _send: Send,
    ) -> None:
        nonlocal called
        called = True
        assert scope["type"] == "websocket"

    middleware = ASGIObservabilityMiddleware(app)

    async def send(_message: Message) -> None:
        return None

    await middleware({"type": "websocket"}, _receive, send)

    assert called is True


def test_instrument_asgi_application_wraps_correlation_only() -> None:
    async def app(
        _scope: Scope,
        _receive: Receive,
        _send: Send,
    ) -> None:
        return None

    instrumented = instrument_asgi_application(
        app,
        Settings(SME_OTEL_ENABLED=False),
    )

    assert isinstance(instrumented, ASGIObservabilityMiddleware)


def test_instrument_asgi_application_wraps_opentelemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapped_apps: list[object] = []

    class FakeOpenTelemetryMiddleware:
        def __init__(self, app: object) -> None:
            wrapped_apps.append(app)

    fake_module = ModuleType("opentelemetry.instrumentation.asgi")
    cast(
        Any,
        fake_module,
    ).OpenTelemetryMiddleware = FakeOpenTelemetryMiddleware
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.instrumentation.asgi",
        fake_module,
    )
    monkeypatch.setattr(
        "sme_sidecar_sdk.integrations.asgi.configure_tracing",
        lambda _settings: None,
    )

    async def app(
        _scope: Scope,
        _receive: Receive,
        _send: Send,
    ) -> None:
        return None

    instrumented = instrument_asgi_application(
        app,
        Settings(SME_OTEL_ENABLED=True),
    )

    assert isinstance(wrapped_apps[0], ASGIObservabilityMiddleware)
    assert isinstance(
        cast(ASGIApp | object, instrumented),
        FakeOpenTelemetryMiddleware,
    )
