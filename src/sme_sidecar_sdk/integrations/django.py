"""Integração de observabilidade para aplicações Django."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Generic, Protocol, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from ..config import Settings, get_settings
from ..observability import get_tracer, request_context
from ..observability.logging import get_logger

log = get_logger(__name__)


class _Request(Protocol):
    """Campos do HttpRequest usados pela integração."""

    @property
    def headers(self) -> Mapping[str, str]:
        """Retorna os headers recebidos."""
        ...

    @property
    def method(self) -> str:
        """Retorna o método HTTP."""
        ...

    @property
    def path(self) -> str:
        """Retorna o caminho da requisição."""
        ...

    request_id: str


class _Response(Protocol):
    """Campos do HttpResponse usados pela integração."""

    @property
    def status_code(self) -> int:
        """Retorna o status HTTP da resposta."""
        ...

    def __setitem__(self, key: str, value: str) -> None:
        """Define um header na resposta.

        Args:
            key: Nome do header.
            value: Valor atribuído ao header.
        """
        ...


RequestT = TypeVar("RequestT", bound=_Request)
ResponseT = TypeVar("ResponseT", bound=_Response)


class ObservabilityMiddleware(
    Generic[RequestT, ResponseT],  # noqa: UP046
):
    """Ativa correlação, tracing e logging para cada requisição Django."""

    def __init__(
        self,
        get_response: Callable[[RequestT], ResponseT],
    ) -> None:
        """Inicializa o middleware com o próximo callable da cadeia."""
        self.get_response = get_response
        self.settings: Settings = get_settings()
        self.tracer: trace.Tracer = get_tracer(__name__)

    def __call__(self, request: RequestT) -> ResponseT:
        """Processa uma requisição dentro do contexto da SDK."""
        started_at = time.monotonic()
        response: ResponseT | None = None

        with request_context(request.headers, self.settings) as current:
            request.request_id = current.request_id
            span_name = f"{request.method} {request.path}"
            with self.tracer.start_as_current_span(span_name) as span:
                span.set_attribute("http.request.method", request.method)
                span.set_attribute("url.path", request.path)
                try:
                    response = self.get_response(request)
                    span.set_attribute(
                        "http.response.status_code",
                        response.status_code,
                    )
                    if response.status_code >= 500:
                        span.set_attribute(
                            "error.type",
                            str(response.status_code),
                        )
                        span.set_status(Status(StatusCode.ERROR))
                    return response
                finally:
                    duration_ms = round(
                        (time.monotonic() - started_at) * 1000,
                        2,
                    )
                    status_code = (
                        response.status_code if response is not None else 500
                    )
                    log_method = log.error if status_code >= 500 else log.info
                    log_method(
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

    def process_exception(
        self,
        request: RequestT,
        exception: Exception,
    ) -> None:
        """Registra no span uma exceção levantada pela view.

        Args:
            request: Requisição que estava sendo processada.
            exception: Exceção levantada pela view.
        """
        span = trace.get_current_span()
        exception_type = (
            f"{type(exception).__module__}.{type(exception).__qualname__}"
        )
        span.record_exception(exception)
        span.set_attribute("error.type", exception_type)
        span.set_status(Status(StatusCode.ERROR, str(exception)))
