"""SME Sidecar SDK: runtime de resiliência in-process.

Entrega timeouts HTTP padronizados, retry com backoff exponencial e
circuit breaker, configurados por convenção a partir de variáveis de
ambiente ``SME_*``.

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

__all__ = [
    "CircuitOpenError",
    "RequestTimeoutError",
    "Settings",
    "UpstreamHTTPError",
    "get_settings",
    "runtime",
]

__version__ = "0.1.0"
