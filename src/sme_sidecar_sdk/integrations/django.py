"""Integração de observabilidade para aplicações Django."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Protocol

from opentelemetry import trace

from ..config import Settings, get_settings
from ..logging import get_logger
from ..observability import get_tracer, request_context

log = get_logger(__name__)


class _Request(Protocol):
    """Campos do HttpRequest usados pela integração."""

    headers: Mapping[str, str]
    method: str
    path: str
    request_id: str


class _Response(Protocol):
    """Campos do HttpResponse usados pela integração."""

    status_code: int

    def __setitem__(self, key: str, value: str) -> None:
        """Define um header na resposta.

        Args:
            key: Nome do header.
            value: Valor atribuído ao header.
        """
        ...


class ObservabilityMiddleware:
    """Ativa correlação, tracing e logging para cada requisição Django."""

    def __init__(
        self,
        get_response: Callable[[_Request], _Response],
    ) -> None:
        """Inicializa o middleware com o próximo callable da cadeia."""
        self.get_response = get_response
        self.settings: Settings = get_settings()
        self.tracer: trace.Tracer = get_tracer(__name__)

    def __call__(self, request: _Request) -> _Response:
        """Processa uma requisição dentro do contexto da SDK."""
        started_at = time.monotonic()
        response: _Response | None = None

        with request_context(request.headers, self.settings) as current:
            request.request_id = current.request_id
            with self.tracer.start_as_current_span("django.request") as span:
                span.set_attribute("http.request.method", request.method)
                span.set_attribute("url.path", request.path)
                try:
                    response = self.get_response(request)
                    span.set_attribute(
                        "http.response.status_code",
                        response.status_code,
                    )
                    return response
                finally:
                    duration_ms = round(
                        (time.monotonic() - started_at) * 1000,
                        2,
                    )
                    status_code = (
                        response.status_code if response is not None else 500
                    )
                    log.info(
                        "http_request_completed",
                        http_method=request.method,
                        http_path=request.path,
                        http_status_code=status_code,
                        http_duration_ms=duration_ms,
                    )
                    if response is not None:
                        response[self.settings.correlation_id_header] = (
                            current.request_id
                        )
