"""Política de retry apoiada em :mod:`tenacity`.

Expõe :func:`retry_policy`, uma fábrica enxuta que monta o Tenacity
utilizando as configurações fornecidas por
:class:`sme_sidecar_sdk.config.Settings`. Quando o retry está
desabilitado, o decorador resultante torna-se um no-op.

Example:
    >>> from sme_sidecar_sdk.resilience.retry import retry_policy
    >>> @retry_policy()
    ... def fetch():
    ...     return httpx.get("https://example.org")
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from tenacity import (
    Retrying,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import Settings, get_settings

F = TypeVar("F", bound=Callable[..., Any])

DEFAULT_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
)


def _build_retrying(
    settings: Settings,
    exceptions: tuple[type[BaseException], ...],
    reraise: bool,
) -> Retrying:
    """Monta um ``Retrying`` do Tenacity a partir das configurações."""
    return Retrying(
        stop=stop_after_attempt(settings.retry_attempts),
        wait=wait_exponential(
            multiplier=1,
            min=settings.retry_backoff_min,
            max=settings.retry_backoff_max,
        ),
        retry=retry_if_exception_type(exceptions),
        reraise=reraise,
    )


def retry_policy(
    *,
    settings: Settings | None = None,
    exceptions: tuple[type[BaseException], ...] = DEFAULT_RETRYABLE_EXCEPTIONS,
    reraise: bool = True,
) -> Callable[[F], F]:
    """Retorna um decorador Tenacity configurado a partir do SDK.

    Args:
        settings: Override opcional para as configurações do SDK.
        exceptions: Tupla de tipos de exceção que disparam uma nova
            tentativa.
        reraise: Quando ``True``, a exceção original é reerguida após a
            última tentativa; caso contrário, o ``RetryError`` do
            Tenacity é levantado.

    Returns:
        Callable[[F], F]: Decorador que envolve o callable alvo.
    """
    settings = settings or get_settings()

    if not settings.retry_enabled or settings.retry_attempts <= 1:

        def passthrough(func: F) -> F:
            return func

        return passthrough

    return retry(  # type: ignore[no-any-return, unused-ignore]
        stop=stop_after_attempt(settings.retry_attempts),
        wait=wait_exponential(
            multiplier=1,
            min=settings.retry_backoff_min,
            max=settings.retry_backoff_max,
        ),
        retry=retry_if_exception_type(exceptions),
        reraise=reraise,
    )


def build_retrying(
    *,
    settings: Settings | None = None,
    exceptions: tuple[type[BaseException], ...] = DEFAULT_RETRYABLE_EXCEPTIONS,
    reraise: bool = True,
) -> Retrying:
    """Retorna um :class:`tenacity.Retrying` para uso explícito.

    Útil quando o chamador precisa de controle direto sobre o motor do
    Tenacity em vez de utilizá-lo via decorador.

    Args:
        settings: Override opcional para as configurações do SDK.
        exceptions: Tupla de tipos de exceção que disparam uma nova
            tentativa.
        reraise: Quando ``True``, a exceção original é reerguida após a
            última tentativa.

    Returns:
        Retrying: Motor Tenacity configurado.
    """
    settings = settings or get_settings()
    return _build_retrying(settings, exceptions, reraise)
