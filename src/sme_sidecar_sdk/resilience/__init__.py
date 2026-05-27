"""Primitivos de resiliência: timeout, retry e circuit breaker."""

from .circuit_breaker import build_circuit_breaker, get_circuit_breaker
from .retry import retry_policy
from .timeout import build_async_client, build_sync_client, build_timeout

__all__ = [
    "build_async_client",
    "build_circuit_breaker",
    "build_sync_client",
    "build_timeout",
    "get_circuit_breaker",
    "retry_policy",
]
