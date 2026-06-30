"""SME Sidecar SDK: resiliência e observabilidade in-process.

Entrega timeouts HTTP padronizados, retry com backoff exponencial e
circuit breaker, além de logging estruturado, correlação e tracing
distribuído. Os recursos são configurados por convenção a partir de
variáveis de ambiente ``SME_*``.

Example:
    >>> from sme_sidecar_sdk import runtime
    >>> runtime.configure()
"""

from __future__ import annotations

from . import runtime
from .config import Settings, get_settings
from .exceptions import (
    CircuitOpenError,
    RequestTimeoutError,
    UpstreamHTTPError,
)
from .http import build_async_http_client, build_http_client
from .observability.context import (
    correlation_context,
    get_correlation_id,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)
from .observability.logging import configure_logging, get_logger

__all__ = [
    "CircuitOpenError",
    "RequestTimeoutError",
    "Settings",
    "UpstreamHTTPError",
    "build_async_http_client",
    "build_http_client",
    "configure_logging",
    "correlation_context",
    "get_correlation_id",
    "get_logger",
    "get_settings",
    "new_correlation_id",
    "reset_correlation_id",
    "runtime",
    "set_correlation_id",
]

__version__ = "0.1.0"
