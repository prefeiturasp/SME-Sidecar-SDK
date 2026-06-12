"""Contexto unificado para requisições recebidas."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass

from ..config import Settings, get_settings
from ..correlation import correlation_context
from .tracing import use_trace_context


@dataclass(frozen=True)
class RequestContext:
    """Identificadores associados à requisição atual.

    Attributes:
        request_id: Identificador de correlação da requisição.
    """

    request_id: str


@contextmanager
def request_context(
    headers: Mapping[str, str],
    settings: Settings | None = None,
) -> Iterator[RequestContext]:
    """Ativa correlação e contexto W3C durante uma requisição recebida.

    Args:
        headers: Headers recebidos com a requisição.
        settings: Configuração opcional. Quando omitida, utiliza a instância
            cacheada do SDK.

    Yields:
        Contexto com os identificadores ativos durante o processamento.
    """
    settings = settings or get_settings()
    with (
        correlation_context(
            headers,
            header_name=settings.correlation_id_header,
        ) as request_id,
        use_trace_context(headers),
    ):
        yield RequestContext(request_id=request_id)
