"""Integração de observabilidade para aplicações ASGI."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Iterable, MutableMapping
from importlib import import_module
from typing import Any, TypeAlias, cast

from ..config import Settings, get_settings
from ..observability.context import correlation_context
from ..observability.logging import get_logger
from ..observability.tracing import configure_tracing

Scope: TypeAlias = MutableMapping[str, Any]  # noqa: UP040
Message: TypeAlias = MutableMapping[str, Any]  # noqa: UP040
Receive: TypeAlias = Callable[[], Awaitable[Message]]  # noqa: UP040
Send: TypeAlias = Callable[[Message], Awaitable[None]]  # noqa: UP040
ASGIApp: TypeAlias = Callable[  # noqa: UP040
    [Scope, Receive, Send],
    Awaitable[None],
]

log = get_logger(__name__)


class ASGIObservabilityMiddleware:
    """Ativa correlação e logging para cada requisição ASGI HTTP."""

    def __init__(
        self,
        app: ASGIApp,
        settings: Settings | None = None,
    ) -> None:
        """Inicializa o middleware ASGI.

        Args:
            app: Aplicação ASGI envolvida.
            settings: Configuração opcional do SDK.
        """
        self.app = app
        self.settings = settings or get_settings()

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Processa o escopo ASGI dentro do contexto da SDK."""
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        started_at = time.monotonic()
        status_code = 500
        headers = _headers_from_scope(scope.get("headers", ()))

        with correlation_context(
            headers,
            header_name=self.settings.correlation_id_header,
        ) as request_id:
            scope["request_id"] = request_id

            async def observed_send(message: Message) -> None:
                nonlocal status_code
                if message.get("type") == "http.response.start":
                    status_code = int(message.get("status", status_code))
                    _set_response_header(
                        message,
                        self.settings.correlation_id_header,
                        request_id,
                    )
                await send(message)

            try:
                await self.app(scope, receive, observed_send)
            finally:
                duration_ms = round(
                    (time.monotonic() - started_at) * 1000,
                    2,
                )
                log_method = log.error if status_code >= 500 else log.info
                log_method(
                    "http_request_completed",
                    http_method=str(scope.get("method", "")),
                    http_path=str(scope.get("path", "")),
                    http_status_code=status_code,
                    http_duration_ms=duration_ms,
                )


def instrument_asgi_application(
    app: ASGIApp,
    settings: Settings | None = None,
) -> ASGIApp:
    """Envolve uma aplicação ASGI com observabilidade da SDK.

    A correlação e o log estruturado são sempre aplicados. O middleware ASGI
    oficial do OpenTelemetry é aplicado somente quando ``SME_OTEL_ENABLED``
    estiver habilitado.

    Args:
        app: Aplicação ASGI a ser envolvida.
        settings: Configuração opcional do SDK.

    Returns:
        Aplicação ASGI instrumentada.

    """
    settings = settings or get_settings()
    instrumented: ASGIApp = ASGIObservabilityMiddleware(app, settings)

    if not settings.otel_enabled:
        return instrumented

    configure_tracing(settings)
    asgi_module: Any = import_module("opentelemetry.instrumentation.asgi")
    return cast(ASGIApp, asgi_module.OpenTelemetryMiddleware(instrumented))


def _headers_from_scope(headers: object) -> dict[str, str]:
    """Converte headers ASGI em dicionário textual."""
    result: dict[str, str] = {}
    if not isinstance(headers, Iterable):
        return result
    for header in headers:
        if not isinstance(header, tuple) or len(header) != 2:
            continue
        raw_name, raw_value = header
        if isinstance(raw_name, bytes) and isinstance(raw_value, bytes):
            result[raw_name.decode("latin1")] = raw_value.decode("latin1")
    return result


def _set_response_header(
    message: Message,
    header_name: str,
    header_value: str,
) -> None:
    """Define header textual na mensagem ASGI de resposta."""
    raw_name = header_name.lower().encode("latin1")
    raw_value = header_value.encode("latin1")
    headers = [
        (name, value)
        for name, value in message.get("headers", [])
        if name.lower() != raw_name
    ]
    headers.append((raw_name, raw_value))
    message["headers"] = headers
