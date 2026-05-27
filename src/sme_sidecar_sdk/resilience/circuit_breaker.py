"""Circuit breaker construído sobre :mod:`pybreaker`.

Fornece um registry de circuit breakers, escopo de processo, indexado
por nome, de modo que chamadores que compartilham o mesmo destino
compartilhem o mesmo estado de breaker.

Example:
    >>> from sme_sidecar_sdk.resilience import get_circuit_breaker
    >>> breaker = get_circuit_breaker("turmas-api")
    >>> @breaker
    ... def call_turmas():
    ...     ...
"""

from __future__ import annotations

import threading

import pybreaker

from ..config import Settings, get_settings

_REGISTRY: dict[str, pybreaker.CircuitBreaker] = {}
_LOCK = threading.Lock()


class _NoopBreaker:
    """Substituto inerte usado quando o circuit breaker está desabilitado."""

    def __call__(self, func):  # type: ignore[no-untyped-def]
        """Retorna ``func`` sem modificações."""
        return func

    def call(self, func, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Invoca ``func`` diretamente, sem a lógica de circuit breaker."""
        return func(*args, **kwargs)


def build_circuit_breaker(
    name: str,
    settings: Settings | None = None,
) -> pybreaker.CircuitBreaker:
    """Constrói uma instância nova de :class:`pybreaker.CircuitBreaker`.

    Args:
        name: Identificador lógico do breaker (utilizado em logs e
            métricas).
        settings: Override opcional para as configurações do SDK.

    Returns:
        pybreaker.CircuitBreaker: Nova instância de breaker.
    """
    settings = settings or get_settings()
    return pybreaker.CircuitBreaker(
        fail_max=settings.circuit_breaker_fail_max,
        reset_timeout=settings.circuit_breaker_reset_timeout,
        name=name,
    )


def get_circuit_breaker(
    name: str,
    settings: Settings | None = None,
) -> pybreaker.CircuitBreaker | _NoopBreaker:
    """Retorna um circuit breaker cacheado por processo para ``name``.

    Quando ``settings.circuit_breaker_enabled`` é ``False``, o objeto
    retornado é um wrapper inerte que preserva a convenção de chamada.

    Args:
        name: Identificador lógico do breaker.
        settings: Override opcional para as configurações do SDK.

    Returns:
        pybreaker.CircuitBreaker | _NoopBreaker: Breaker cacheado ou
        wrapper inerte.
    """
    settings = settings or get_settings()
    if not settings.circuit_breaker_enabled:
        return _NoopBreaker()

    with _LOCK:
        breaker = _REGISTRY.get(name)
        if breaker is None:
            breaker = build_circuit_breaker(name, settings)
            _REGISTRY[name] = breaker
    return breaker


def reset_registry() -> None:
    """Limpa o registry de breakers no processo.

    Útil em testes para evitar contaminação entre casos.
    """
    with _LOCK:
        _REGISTRY.clear()
