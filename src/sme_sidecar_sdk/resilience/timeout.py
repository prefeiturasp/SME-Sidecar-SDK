"""Timeouts HTTP padronizados sobre :mod:`httpx`.

O SDK fornece clientes ``httpx`` prontos para uso (sync e async)
pré-configurados com o timeout definido por
:class:`sme_sidecar_sdk.config.Settings`.

Example:
    >>> from sme_sidecar_sdk.resilience.timeout import build_sync_client
    >>> with build_sync_client() as client:
    ...     response = client.get("https://example.org")
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

import httpx

from ..config import Settings, get_settings
from ..correlation import get_correlation_id


def build_timeout(settings: Settings | None = None) -> httpx.Timeout:
    """Constrói um :class:`httpx.Timeout` a partir das configurações do SDK.

    Args:
        settings: Override opcional. Quando omitido, utiliza a instância
            cacheada do SDK.

    Returns:
        httpx.Timeout: Configuração de timeout aplicada às requisições
        de saída.
    """
    settings = settings or get_settings()
    seconds = settings.timeout_seconds if settings.timeout_enabled else None
    return httpx.Timeout(seconds)


def build_sync_client(
    settings: Settings | None = None,
    **client_kwargs: object,
) -> httpx.Client:
    """Cria um :class:`httpx.Client` síncrono com os padrões do SDK.

    Args:
        settings: Override opcional para as configurações do SDK.
        **client_kwargs: Argumentos adicionais repassados ao
            ``httpx.Client``. A chave ``timeout`` é gerenciada pelo SDK
            e não deve ser informada.

    Returns:
        httpx.Client: Cliente HTTP síncrono configurado.

    Raises:
        ValueError: Quando argumentos reservados são informados.
    """
    settings = settings or get_settings()
    _reject_reserved_kwargs(client_kwargs)
    event_hooks = _merge_event_hooks(
        client_kwargs.pop("event_hooks", None),
        request_hook=_sync_propagation_hook(settings),
    )
    return httpx.Client(
        timeout=build_timeout(settings),
        event_hooks=event_hooks,
        **client_kwargs,  # type: ignore[arg-type, unused-ignore]
    )


def build_async_client(
    settings: Settings | None = None,
    **client_kwargs: object,
) -> httpx.AsyncClient:
    """Cria um :class:`httpx.AsyncClient` assíncrono com os padrões do SDK.

    Args:
        settings: Override opcional para as configurações do SDK.
        **client_kwargs: Argumentos adicionais repassados ao
            ``httpx.AsyncClient``. A chave ``timeout`` é gerenciada pelo
            SDK e não deve ser informada.

    Returns:
        httpx.AsyncClient: Cliente HTTP assíncrono configurado.

    Raises:
        ValueError: Quando argumentos reservados são informados.
    """
    settings = settings or get_settings()
    _reject_reserved_kwargs(client_kwargs)
    event_hooks = _merge_event_hooks(
        client_kwargs.pop("event_hooks", None),
        request_hook=_async_propagation_hook(settings),
    )
    return httpx.AsyncClient(
        timeout=build_timeout(settings),
        event_hooks=event_hooks,
        **client_kwargs,  # type: ignore[arg-type, unused-ignore]
    )


def _reject_reserved_kwargs(kwargs: dict[str, object]) -> None:
    """Rejeita argumentos cuja configuração pertence ao SDK.

    Args:
        kwargs: Argumentos destinados ao construtor do cliente HTTPX.

    Raises:
        ValueError: Se ``timeout`` for informado explicitamente.
    """
    reserved = {"timeout"} & kwargs.keys()
    if reserved:
        raise ValueError(
            "Os argumentos a seguir são gerenciados pelo SDK e não "
            f"podem ser sobrescritos: {sorted(reserved)}"
        )


EventHook = Callable[..., Any]


def _sync_propagation_hook(settings: Settings) -> EventHook:
    """Cria um hook síncrono para propagar o identificador de correlação.

    Args:
        settings: Configuração que define o nome do header.

    Returns:
        Hook de requisição compatível com o cliente HTTPX síncrono.
    """

    def hook(request: httpx.Request) -> None:
        """Adiciona o identificador ativo aos headers da requisição.

        Args:
            request: Requisição HTTPX que será enviada.
        """
        correlation_id = get_correlation_id()
        if correlation_id:
            request.headers.setdefault(
                settings.correlation_id_header,
                correlation_id,
            )

    return hook


def _async_propagation_hook(
    settings: Settings,
) -> EventHook:
    """Cria um hook assíncrono para propagar a correlação.

    Args:
        settings: Configuração que define o nome do header.

    Returns:
        Hook de requisição compatível com o cliente HTTPX assíncrono.
    """

    async def hook(request: httpx.Request) -> None:
        """Adiciona o identificador ativo aos headers da requisição.

        Args:
            request: Requisição HTTPX que será enviada.
        """
        correlation_id = get_correlation_id()
        if correlation_id:
            request.headers.setdefault(
                settings.correlation_id_header,
                correlation_id,
            )

    return hook


def _merge_event_hooks(
    existing: object,
    *,
    request_hook: EventHook,
) -> dict[str, list[EventHook]]:
    """Combina hooks existentes com o hook de propagação do SDK.

    Args:
        existing: Mapeamento de hooks recebido pela aplicação.
        request_hook: Hook de propagação que deve executar primeiro.

    Returns:
        Cópia dos hooks com o hook do SDK no início da lista de requisição.
    """
    hooks: dict[str, list[EventHook]] = {}
    if isinstance(existing, Mapping):
        hooks = {
            str(name): list(cast(list[EventHook], callbacks))
            for name, callbacks in existing.items()
        }
    request_hooks = list(hooks.get("request", []))
    request_hooks.insert(0, request_hook)
    hooks["request"] = request_hooks
    return hooks
