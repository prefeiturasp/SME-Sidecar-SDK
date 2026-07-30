"""Contratos públicos de tipagem para clientes HTTP da SDK."""

from __future__ import annotations

from typing import Any, Protocol

import httpx


class SyncHTTPClient(Protocol):
    """Contrato de tipo para clientes HTTP síncronos.

    Destinado a anotações de tipo quando o código consumidor precisa
    chamar métodos HTTP comuns sem depender da classe concreta retornada
    por ``build_http_client``.
    """

    def get(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Declara a assinatura para solicitar um recurso ao upstream.

        Args:
            url: URL absoluta ou relativa à ``base_url`` do cliente.
            **kwargs: Argumentos repassados ao cliente HTTP.

        Returns:
            Resposta HTTP retornada pelo upstream.
        """
        ...

    def post(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Declara a assinatura para criar ou submeter dados ao upstream.

        Args:
            url: URL absoluta ou relativa à ``base_url`` do cliente.
            **kwargs: Argumentos repassados ao cliente HTTP.

        Returns:
            Resposta HTTP retornada pelo upstream.
        """
        ...

    def put(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Declara a assinatura para substituir um recurso no upstream.

        Args:
            url: URL absoluta ou relativa à ``base_url`` do cliente.
            **kwargs: Argumentos repassados ao cliente HTTP.

        Returns:
            Resposta HTTP retornada pelo upstream.
        """
        ...

    def patch(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Declara a assinatura para atualizar parcialmente um recurso.

        Args:
            url: URL absoluta ou relativa à ``base_url`` do cliente.
            **kwargs: Argumentos repassados ao cliente HTTP.

        Returns:
            Resposta HTTP retornada pelo upstream.
        """
        ...

    def delete(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Declara a assinatura para remover um recurso no upstream.

        Args:
            url: URL absoluta ou relativa à ``base_url`` do cliente.
            **kwargs: Argumentos repassados ao cliente HTTP.

        Returns:
            Resposta HTTP retornada pelo upstream.
        """
        ...

    def close(self) -> None:
        """Declara a assinatura para liberar recursos do cliente."""
        ...


class AsyncHTTPClientProtocol(Protocol):
    """Contrato de tipo para clientes HTTP assíncronos.

    Destinado a anotações de tipo quando o código consumidor precisa
    chamar métodos HTTP com ``await`` sem depender da classe concreta
    retornada por ``build_async_http_client``.
    """

    async def get(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Declara a assinatura para solicitar um recurso ao upstream.

        Args:
            url: URL absoluta ou relativa à ``base_url`` do cliente.
            **kwargs: Argumentos repassados ao cliente HTTP.

        Returns:
            Resposta HTTP retornada pelo upstream.
        """
        ...

    async def post(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Declara a assinatura para criar ou submeter dados ao upstream.

        Args:
            url: URL absoluta ou relativa à ``base_url`` do cliente.
            **kwargs: Argumentos repassados ao cliente HTTP.

        Returns:
            Resposta HTTP retornada pelo upstream.
        """
        ...

    async def put(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Declara a assinatura para substituir um recurso no upstream.

        Args:
            url: URL absoluta ou relativa à ``base_url`` do cliente.
            **kwargs: Argumentos repassados ao cliente HTTP.

        Returns:
            Resposta HTTP retornada pelo upstream.
        """
        ...

    async def patch(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Declara a assinatura para atualizar parcialmente um recurso.

        Args:
            url: URL absoluta ou relativa à ``base_url`` do cliente.
            **kwargs: Argumentos repassados ao cliente HTTP.

        Returns:
            Resposta HTTP retornada pelo upstream.
        """
        ...

    async def delete(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Declara a assinatura para remover um recurso no upstream.

        Args:
            url: URL absoluta ou relativa à ``base_url`` do cliente.
            **kwargs: Argumentos repassados ao cliente HTTP.

        Returns:
            Resposta HTTP retornada pelo upstream.
        """
        ...

    async def aclose(self) -> None:
        """Declara a assinatura para liberar recursos do cliente."""
        ...
