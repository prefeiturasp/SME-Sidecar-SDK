"""Fachada de alto nível que expõe o ponto de entrada ``configure()``.

Este módulo é a superfície de importação estável para os consumidores
(``from sme_sidecar_sdk import runtime; runtime.configure()``). Carrega
as ``Settings`` uma vez e expõe os toggles ativos por meio de
:class:`RuntimeState`.

Example:
    >>> from sme_sidecar_sdk import runtime
    >>> state = runtime.configure()
    >>> state.settings.timeout_seconds
    10.0
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings, get_settings, reset_settings_cache
from .observability.logging import (
    configure_logging,
    get_logger,
    shutdown_logging,
)
from .observability.tracing import configure_tracing, shutdown_tracing


@dataclass(frozen=True)
class RuntimeState:
    """Snapshot dos primitivos de resiliência ativos no processo.

    Attributes:
        settings: Configuração efetiva utilizada durante o ``configure``.
        timeout_enabled: ``True`` quando o wrapper de timeout padronizado
            está habilitado.
        retry_enabled: ``True`` quando o decorador de retry está habilitado.
        circuit_breaker_enabled: ``True`` quando o circuit breaker está
            habilitado.
        logging_enabled: ``True`` quando os logs estruturados estão ativos.
        tracing_enabled: ``True`` quando o provider OpenTelemetry está ativo.
    """

    settings: Settings
    timeout_enabled: bool
    retry_enabled: bool
    circuit_breaker_enabled: bool
    logging_enabled: bool
    tracing_enabled: bool


_STATE: RuntimeState | None = None


def configure(settings: Settings | None = None) -> RuntimeState:
    """Inicializa o runtime do SDK no processo atual.

    Idempotente: chamadas subsequentes reavaliam as configurações
    ativas. Quando ``SME_SDK_ENABLED`` é ``False``, o estado devolvido
    reporta todos os subsistemas como desabilitados.

    Args:
        settings: Configuração opcional. Quando omitida, utiliza a
            instância cacheada por :func:`sme_sidecar_sdk.config.get_settings`.

    Returns:
        RuntimeState: Snapshot dos primitivos de resiliência ativos.
    """
    global _STATE
    settings = settings or get_settings()

    if not settings.enabled:
        shutdown_logging()
        _STATE = RuntimeState(
            settings=settings,
            timeout_enabled=False,
            retry_enabled=False,
            circuit_breaker_enabled=False,
            logging_enabled=False,
            tracing_enabled=False,
        )
        return _STATE

    configure_logging(settings)
    tracer_provider = configure_tracing(settings)
    _STATE = RuntimeState(
        settings=settings,
        timeout_enabled=settings.timeout_enabled,
        retry_enabled=settings.retry_enabled,
        circuit_breaker_enabled=settings.circuit_breaker_enabled,
        logging_enabled=settings.logging_enabled,
        tracing_enabled=tracer_provider is not None,
    )
    if settings.logging_enabled:
        get_logger(__name__).info(
            "sdk_configured",
            tracing_enabled=_STATE.tracing_enabled,
        )
    return _STATE


def state() -> RuntimeState | None:
    """Retorna o estado capturado pela última chamada a :func:`configure`."""
    return _STATE


def shutdown() -> None:
    """Libera o estado do runtime do SDK.

    Limpa o snapshot capturado por :func:`configure` e o cache das
    configurações, devolvendo o processo ao estado anterior ao boot.
    """
    global _STATE
    shutdown_logging()
    shutdown_tracing()
    _STATE = None
    reset_settings_cache()
