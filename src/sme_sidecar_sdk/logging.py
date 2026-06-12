"""Configuração centralizada de logs estruturados."""

from __future__ import annotations

import atexit
import logging
import sys
from typing import Any, cast

import structlog
from structlog.types import EventDict, Processor

from .config import Settings, get_settings
from .correlation import get_correlation_id
from .log_providers.base import LogProvider
from .log_providers.factory import build_log_providers

_LOG_PROVIDERS: list[LogProvider] = []


def _add_service_context(settings: Settings) -> Processor:
    """Cria processor que adiciona identidade do serviço ao evento."""

    def processor(_: Any, __: str, event_dict: EventDict) -> EventDict:
        """Adiciona a identidade do serviço ao evento.

        Args:
            _: Logger que originou o evento.
            __: Nome do método de logging utilizado.
            event_dict: Campos estruturados do evento.

        Returns:
            Evento enriquecido com serviço e ambiente.
        """
        event_dict.setdefault("service", settings.service_name)
        event_dict.setdefault("environment", settings.environment)
        return event_dict

    return processor


def _add_correlation_context(
    _: Any,
    __: str,
    event_dict: EventDict,
) -> EventDict:
    """Adiciona o identificador de correlação ativo ao evento.

    Args:
        _: Logger que originou o evento.
        __: Nome do método de logging utilizado.
        event_dict: Campos estruturados do evento.

    Returns:
        Evento enriquecido com o request ID, quando disponível.
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict.setdefault("request_id", correlation_id)
    return event_dict


def _add_trace_context(_: Any, __: str, event_dict: EventDict) -> EventDict:
    """Adiciona os identificadores do span ativo ao evento.

    Args:
        _: Logger que originou o evento.
        __: Nome do método de logging utilizado.
        event_dict: Campos estruturados do evento.

    Returns:
        Evento enriquecido com trace ID e span ID, quando disponíveis.
    """
    from opentelemetry import trace

    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        event_dict.setdefault("trace_id", f"{span_context.trace_id:032x}")
        event_dict.setdefault("span_id", f"{span_context.span_id:016x}")
    return event_dict


def _build_formatter(
    shared_processors: list[Processor],
    renderer: Processor,
) -> logging.Formatter:
    """Cria um formatter compatível com logging e structlog."""
    return cast(
        logging.Formatter,
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        ),
    )


def configure_logging(settings: Settings | None = None) -> None:
    """Configura structlog e logging padrão com o mesmo formato.

    Args:
        settings: Configuração opcional. Quando omitida, utiliza a instância
            cacheada do SDK.
    """
    global _LOG_PROVIDERS
    settings = settings or get_settings()
    shutdown_logging()
    if not settings.logging_enabled:
        return

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_service_context(settings),
        _add_correlation_context,
        _add_trace_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer: Processor
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    formatter = _build_formatter(shared_processors, renderer)
    provider_formatter = _build_formatter(
        shared_processors,
        structlog.processors.JSONRenderer(),
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(settings.log_level)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(console_handler)
    _LOG_PROVIDERS = build_log_providers(settings)
    for provider in _LOG_PROVIDERS:
        root.addHandler(provider.build_handler(provider_formatter))
    root.setLevel(settings.log_level)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[settings.log_level]
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def shutdown_logging() -> None:
    """Encerra providers externos configurados para logging."""
    global _LOG_PROVIDERS
    for provider in _LOG_PROVIDERS:
        provider.shutdown()
    _LOG_PROVIDERS = []


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Retorna logger estruturado opcionalmente nomeado.

    Args:
        name: Nome associado ao logger.

    Returns:
        Logger estruturado vinculado ao nome informado.
    """
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


atexit.register(shutdown_logging)
