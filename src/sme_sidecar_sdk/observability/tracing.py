"""Tracing distribuído com OpenTelemetry e exportação OTLP."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from contextlib import contextmanager
from urllib.parse import unquote

from opentelemetry import context, propagate, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from ..config import Settings, get_settings

_PROVIDER: TracerProvider | None = None
_HTTPX_INSTRUMENTED = False


def _parse_headers(value: str) -> tuple[tuple[str, str], ...]:
    """Converte a configuração textual de headers OTLP em pares.

    Args:
        value: Lista de headers separados por vírgula no formato
            ``chave=valor``.

    Returns:
        Pares de nome e valor com nomes normalizados em minúsculas.

    Raises:
        ValueError: Se algum item não usar o formato ``chave=valor``.
    """
    headers: list[tuple[str, str]] = []
    for item in value.split(","):
        if not item.strip():
            continue
        name, separator, raw_value = item.partition("=")
        if not separator or not name.strip():
            raise ValueError(
                "SME_OTEL_EXPORTER_OTLP_HEADERS deve usar chave=valor"
            )
        headers.append((name.strip().lower(), unquote(raw_value.strip())))
    return tuple(headers)


def configure_tracing(
    settings: Settings | None = None,
) -> TracerProvider | None:
    """Configura provider OTLP e instrumentação automática do HTTPX.

    Args:
        settings: Configuração opcional. Quando omitida, utiliza a instância
            cacheada do SDK.

    Returns:
        Provider configurado ou ``None`` quando tracing está desabilitado.

    Raises:
        ValueError: Se os headers OTLP não usarem o formato ``chave=valor``.
    """
    global _HTTPX_INSTRUMENTED, _PROVIDER
    settings = settings or get_settings()
    if not settings.otel_enabled:
        return None
    if _PROVIDER is not None:
        return _PROVIDER

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": settings.service_version,
            "deployment.environment": settings.environment,
            "deployment.environment.name": settings.environment,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        headers=_parse_headers(settings.otel_exporter_otlp_headers),
        insecure=settings.otel_exporter_otlp_insecure,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    if not _HTTPX_INSTRUMENTED:
        HTTPXClientInstrumentor().instrument(tracer_provider=provider)
        _HTTPX_INSTRUMENTED = True
    _PROVIDER = provider
    return provider


def get_tracer(name: str) -> trace.Tracer:
    """Retorna tracer associado ao módulo informado.

    Args:
        name: Nome da biblioteca ou do módulo instrumentado.

    Returns:
        Tracer associado ao provider ativo.
    """
    if _PROVIDER is not None:
        return _PROVIDER.get_tracer(name)
    return trace.get_tracer(name)


def inject_trace_context(headers: MutableMapping[str, str]) -> None:
    """Injeta o contexto W3C ativo em headers de saída.

    Args:
        headers: Headers mutáveis que receberão o contexto distribuído.
    """
    propagate.inject(headers)


def extract_trace_context(headers: Mapping[str, str]) -> context.Context:
    """Extrai contexto W3C de headers recebidos.

    Args:
        headers: Headers recebidos com a requisição.

    Returns:
        Contexto OpenTelemetry extraído dos headers.
    """
    carrier = {name.casefold(): value for name, value in headers.items()}
    return propagate.extract(carrier)


@contextmanager
def use_trace_context(headers: Mapping[str, str]) -> Iterator[context.Context]:
    """Ativa temporariamente o contexto distribuído recebido.

    Args:
        headers: Headers usados para extrair o contexto distribuído.

    Yields:
        Contexto OpenTelemetry ativo durante o escopo.
    """
    extracted = extract_trace_context(headers)
    token = context.attach(extracted)
    try:
        yield extracted
    finally:
        context.detach(token)


def shutdown_tracing() -> None:
    """Força o envio dos spans pendentes e encerra o provider."""
    if _PROVIDER is not None:
        _PROVIDER.force_flush()
