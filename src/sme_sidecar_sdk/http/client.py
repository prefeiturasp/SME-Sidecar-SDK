"""Wrapper HTTP compartilhado para comunicação entre serviços."""

from __future__ import annotations

from asyncio import sleep
from collections.abc import Awaitable, Callable, Mapping
from time import perf_counter
from types import TracebackType
from typing import Any, Self, cast

import httpx
from tenacity import (
    AsyncRetrying,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import Settings, get_settings
from ..observability.context import get_correlation_id
from ..observability.logging import get_logger
from ..observability.tracing import inject_trace_context
from ..resilience.circuit_breaker import get_circuit_breaker
from ..resilience.timeout import build_async_client, build_sync_client

_RETRYABLE_HTTP_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.TransportError,
)
EventHook = Callable[..., Any]


class _BaseHTTPClient:
    """Base interna com estado e logging compartilhados."""

    def __init__(self, name: str, settings: Settings | None = None) -> None:
        """Inicializa dependências comuns aos clientes HTTP.

        Args:
            name: Nome lógico do upstream.
            settings: Configuração opcional da SDK.
        """
        self.name = name
        self.settings = settings or get_settings()
        self._breaker = get_circuit_breaker(name, self.settings)
        self._logger = get_logger(__name__)

    def _prepare_client_kwargs(
        self,
        base_url: str | httpx.URL | None,
        client_kwargs: dict[str, object],
        request_hook: EventHook,
    ) -> dict[str, object]:
        """Prepara argumentos repassados ao cliente HTTPX.

        Args:
            base_url: URL base opcional do upstream.
            client_kwargs: Argumentos recebidos pela factory pública.
            request_hook: Hook de propagação do contexto ativo.

        Returns:
            Cópia dos argumentos com ``base_url`` e ``event_hooks`` ajustados.
        """
        prepared = dict(client_kwargs)
        if base_url is not None:
            prepared["base_url"] = base_url
        prepared["event_hooks"] = _merge_event_hooks(
            prepared.get("event_hooks"),
            request_hook=request_hook,
        )
        return prepared

    def _log_success(
        self,
        method: str,
        response: httpx.Response,
        started_at: float,
    ) -> None:
        """Registra sucesso de uma chamada HTTP de saída.

        Args:
            method: Método HTTP executado.
            response: Resposta recebida do upstream.
            started_at: Instante de início medido por ``perf_counter``.
        """
        self._logger.info(
            "http_client_request_completed",
            upstream=self.name,
            http_method=method.upper(),
            http_url=str(response.request.url),
            http_path=response.request.url.path,
            http_status_code=response.status_code,
            http_duration_ms=_duration_ms(started_at),
            retry_enabled=self.settings.retry_enabled,
            circuit_breaker_enabled=self.settings.circuit_breaker_enabled,
        )

    def _log_failure(
        self,
        method: str,
        url: str | httpx.URL,
        started_at: float,
        exc: Exception,
    ) -> None:
        """Registra falha de uma chamada HTTP de saída.

        Args:
            method: Método HTTP executado.
            url: URL solicitada.
            started_at: Instante de início medido por ``perf_counter``.
            exc: Exceção capturada durante a chamada.
        """
        event: dict[str, object] = {
            "upstream": self.name,
            "http_method": method.upper(),
            "http_url": str(url),
            "http_duration_ms": _duration_ms(started_at),
            "retry_enabled": self.settings.retry_enabled,
            "circuit_breaker_enabled": self.settings.circuit_breaker_enabled,
            "error_type": type(exc).__name__,
        }
        if isinstance(exc, httpx.HTTPStatusError):
            event["http_status_code"] = exc.response.status_code
            event["http_path"] = exc.request.url.path
            event["http_url"] = str(exc.request.url)
        self._logger.error("http_client_request_failed", **event)


class HTTPClient(_BaseHTTPClient):
    """Cliente HTTP síncrono com capacidades técnicas da SDK.

    Args:
        name: Nome lógico do upstream usado em logs e circuit breaker.
        base_url: URL base opcional repassada ao ``httpx.Client``.
        settings: Configuração opcional. Quando omitida, utiliza a
            configuração cacheada da SDK.
        **client_kwargs: Argumentos adicionais repassados ao cliente HTTPX
            construído pela SDK.
    """

    def __init__(
        self,
        name: str,
        *,
        base_url: str | httpx.URL | None = None,
        settings: Settings | None = None,
        **client_kwargs: object,
    ) -> None:
        """Inicializa o cliente síncrono compartilhado."""
        super().__init__(name, settings)
        prepared_kwargs = self._prepare_client_kwargs(
            base_url,
            client_kwargs,
            _sync_propagation_hook(self.settings),
        )
        self._client = build_sync_client(self.settings, **prepared_kwargs)

    def __enter__(self) -> Self:
        """Entra no contexto do cliente HTTP."""
        self._client.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Fecha o cliente HTTP ao sair do contexto."""
        self._client.__exit__(exc_type, exc_value, traceback)

    def close(self) -> None:
        """Fecha conexões mantidas pelo cliente HTTP."""
        self._client.close()

    def request(
        self,
        method: str,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa uma requisição HTTP com retry, breaker e logging.

        Args:
            method: Método HTTP.
            url: URL absoluta ou relativa à ``base_url``.
            **kwargs: Argumentos repassados ao ``httpx.Client.request``.

        Returns:
            Resposta HTTPX validada com ``raise_for_status()``.

        Raises:
            httpx.TimeoutException: Quando a chamada expira.
            httpx.RequestError: Quando ocorre falha de transporte.
            httpx.HTTPStatusError: Quando a resposta é 4xx ou 5xx.
            pybreaker.CircuitBreakerError: Quando o circuito está aberto.
        """

        def call() -> httpx.Response:
            return self._send_with_retry(method, url, **kwargs)

        def protected_call() -> httpx.Response:
            response: httpx.Response = self._breaker.call(call)
            return response

        return self._execute(method, url, protected_call)

    def get(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Executa uma requisição ``GET``."""
        return self.request("GET", url, **kwargs)

    def post(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Executa uma requisição ``POST``."""
        return self.request("POST", url, **kwargs)

    def put(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Executa uma requisição ``PUT``."""
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Executa uma requisição ``PATCH``."""
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Executa uma requisição ``DELETE``."""
        return self.request("DELETE", url, **kwargs)

    def _send(
        self,
        method: str,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        response = self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    def _send_with_retry(
        self,
        method: str,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        if (
            not self.settings.retry_enabled
            or self.settings.retry_attempts <= 1
        ):
            return self._send(method, url, **kwargs)
        retrying = _build_sync_retrying(self.settings)
        for attempt in retrying:
            with attempt:
                return self._send(method, url, **kwargs)
        raise RuntimeError("retry finalizado sem resposta HTTP")

    def _execute(
        self,
        method: str,
        url: str | httpx.URL,
        call: Callable[[], httpx.Response],
    ) -> httpx.Response:
        started_at = perf_counter()
        try:
            response = call()
        except Exception as exc:
            self._log_failure(method, url, started_at, exc)
            raise
        self._log_success(method, response, started_at)
        return response


class AsyncHTTPClient(_BaseHTTPClient):
    """Cliente HTTP assíncrono com capacidades técnicas da SDK.

    Args:
        name: Nome lógico do upstream usado em logs e circuit breaker.
        base_url: URL base opcional repassada ao ``httpx.AsyncClient``.
        settings: Configuração opcional. Quando omitida, utiliza a
            configuração cacheada da SDK.
        **client_kwargs: Argumentos adicionais repassados ao cliente HTTPX
            construído pela SDK.
    """

    def __init__(
        self,
        name: str,
        *,
        base_url: str | httpx.URL | None = None,
        settings: Settings | None = None,
        **client_kwargs: object,
    ) -> None:
        """Inicializa o cliente assíncrono compartilhado."""
        super().__init__(name, settings)
        prepared_kwargs = self._prepare_client_kwargs(
            base_url,
            client_kwargs,
            _async_propagation_hook(self.settings),
        )
        self._client = build_async_client(self.settings, **prepared_kwargs)

    async def __aenter__(self) -> Self:
        """Entra no contexto assíncrono do cliente HTTP."""
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Fecha o cliente HTTP ao sair do contexto assíncrono."""
        await self._client.__aexit__(exc_type, exc_value, traceback)

    async def aclose(self) -> None:
        """Fecha conexões mantidas pelo cliente HTTP assíncrono."""
        await self._client.aclose()

    async def request(
        self,
        method: str,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa uma requisição HTTP assíncrona com retry e breaker.

        Args:
            method: Método HTTP.
            url: URL absoluta ou relativa à ``base_url``.
            **kwargs: Argumentos repassados ao ``httpx.AsyncClient.request``.

        Returns:
            Resposta HTTPX validada com ``raise_for_status()``.

        Raises:
            httpx.TimeoutException: Quando a chamada expira.
            httpx.RequestError: Quando ocorre falha de transporte.
            httpx.HTTPStatusError: Quando a resposta é 4xx ou 5xx.
            pybreaker.CircuitBreakerError: Quando o circuito está aberto.
        """

        async def call() -> httpx.Response:
            return await self._send_with_retry(method, url, **kwargs)

        return await self._execute(
            method,
            url,
            lambda: _call_async_with_breaker(
                self._breaker,
                self.settings,
                call,
            ),
        )

    async def get(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa uma requisição ``GET``."""
        return await self.request("GET", url, **kwargs)

    async def post(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa uma requisição ``POST``."""
        return await self.request("POST", url, **kwargs)

    async def put(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa uma requisição ``PUT``."""
        return await self.request("PUT", url, **kwargs)

    async def patch(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa uma requisição ``PATCH``."""
        return await self.request("PATCH", url, **kwargs)

    async def delete(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa uma requisição ``DELETE``."""
        return await self.request("DELETE", url, **kwargs)

    async def _send_with_retry(
        self,
        method: str,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        if (
            not self.settings.retry_enabled
            or self.settings.retry_attempts <= 1
        ):
            return await self._send(method, url, **kwargs)
        retrying = _build_async_retrying(self.settings)
        async for attempt in retrying:
            with attempt:
                return await self._send(method, url, **kwargs)
        raise RuntimeError("retry finalizado sem resposta HTTP")

    async def _send(
        self,
        method: str,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        response = await self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    async def _execute(
        self,
        method: str,
        url: str | httpx.URL,
        call: Callable[[], Awaitable[httpx.Response]],
    ) -> httpx.Response:
        started_at = perf_counter()
        try:
            response = await call()
        except Exception as exc:
            self._log_failure(method, url, started_at, exc)
            raise
        self._log_success(method, response, started_at)
        return response


def build_http_client(
    name: str,
    *,
    base_url: str | httpx.URL | None = None,
    settings: Settings | None = None,
    **client_kwargs: object,
) -> HTTPClient:
    """Cria um cliente HTTP síncrono compartilhado.

    Args:
        name: Nome lógico do upstream.
        base_url: URL base opcional.
        settings: Configuração opcional da SDK.
        **client_kwargs: Argumentos adicionais repassados ao HTTPX.

    Returns:
        Cliente HTTP síncrono configurado.
    """
    return HTTPClient(
        name,
        base_url=base_url,
        settings=settings,
        **client_kwargs,
    )


def build_async_http_client(
    name: str,
    *,
    base_url: str | httpx.URL | None = None,
    settings: Settings | None = None,
    **client_kwargs: object,
) -> AsyncHTTPClient:
    """Cria um cliente HTTP assíncrono compartilhado.

    Args:
        name: Nome lógico do upstream.
        base_url: URL base opcional.
        settings: Configuração opcional da SDK.
        **client_kwargs: Argumentos adicionais repassados ao HTTPX.

    Returns:
        Cliente HTTP assíncrono configurado.
    """
    return AsyncHTTPClient(
        name,
        base_url=base_url,
        settings=settings,
        **client_kwargs,
    )


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 2)


def _sync_propagation_hook(settings: Settings) -> EventHook:
    """Cria um hook síncrono para propagar contexto da requisição.

    Args:
        settings: Configuração que define o nome do header.

    Returns:
        Hook de requisição compatível com o cliente HTTPX síncrono.
    """

    def hook(request: httpx.Request) -> None:
        """Adiciona contexto ativo aos headers da requisição.

        Args:
            request: Requisição HTTPX que será enviada.
        """
        _propagate_request_context(request, settings)

    return hook


def _async_propagation_hook(settings: Settings) -> EventHook:
    """Cria um hook assíncrono para propagar contexto da requisição.

    Args:
        settings: Configuração que define o nome do header.

    Returns:
        Hook de requisição compatível com o cliente HTTPX assíncrono.
    """

    async def hook(request: httpx.Request) -> None:
        """Adiciona contexto ativo aos headers da requisição.

        Args:
            request: Requisição HTTPX que será enviada.
        """
        _propagate_request_context(request, settings)
        await sleep(0)

    return hook


def _propagate_request_context(
    request: httpx.Request,
    settings: Settings,
) -> None:
    """Propaga headers de correlação e tracing para uma requisição HTTPX.

    Args:
        request: Requisição HTTPX que receberá os headers.
        settings: Configuração que define o nome do header de correlação.
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        request.headers.setdefault(
            settings.correlation_id_header,
            correlation_id,
        )
    inject_trace_context(request.headers)


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


def _build_sync_retrying(settings: Settings) -> Retrying:
    return Retrying(
        stop=stop_after_attempt(settings.retry_attempts),
        wait=wait_exponential(
            multiplier=1,
            min=settings.retry_backoff_min,
            max=settings.retry_backoff_max,
        ),
        retry=retry_if_exception_type(_RETRYABLE_HTTP_EXCEPTIONS),
        reraise=True,
    )


def _build_async_retrying(settings: Settings) -> AsyncRetrying:
    return AsyncRetrying(
        stop=stop_after_attempt(settings.retry_attempts),
        wait=wait_exponential(
            multiplier=1,
            min=settings.retry_backoff_min,
            max=settings.retry_backoff_max,
        ),
        retry=retry_if_exception_type(_RETRYABLE_HTTP_EXCEPTIONS),
        reraise=True,
    )


async def _call_async_with_breaker(
    breaker: Any,
    settings: Settings,
    call: Callable[[], Awaitable[httpx.Response]],
) -> httpx.Response:
    if not settings.circuit_breaker_enabled:
        return await call()

    state = breaker.state
    state.before_call(call)
    for listener in breaker.listeners:
        listener.before_call(breaker, call)
    try:
        response = await call()
    except BaseException as exc:
        state._handle_error(exc)
        raise
    state._handle_success()
    return response
