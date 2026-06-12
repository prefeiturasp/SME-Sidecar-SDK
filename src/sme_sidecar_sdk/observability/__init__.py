"""Primitivos de observabilidade do SDK."""

from .context import (
    RequestContext,
    correlation_context,
    correlation_id_from_headers,
    get_correlation_id,
    new_correlation_id,
    request_context,
    reset_correlation_id,
    set_correlation_id,
)
from .logging import configure_logging, get_logger, shutdown_logging
from .tracing import (
    configure_tracing,
    extract_trace_context,
    get_tracer,
    inject_trace_context,
    shutdown_tracing,
    use_trace_context,
)

__all__ = [
    "RequestContext",
    "configure_logging",
    "configure_tracing",
    "correlation_context",
    "correlation_id_from_headers",
    "extract_trace_context",
    "get_correlation_id",
    "get_logger",
    "get_tracer",
    "inject_trace_context",
    "new_correlation_id",
    "request_context",
    "reset_correlation_id",
    "set_correlation_id",
    "shutdown_logging",
    "shutdown_tracing",
    "use_trace_context",
]
