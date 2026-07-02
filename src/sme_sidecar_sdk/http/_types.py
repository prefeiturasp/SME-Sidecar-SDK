"""Contratos de tipagem para clientes HTTP da SDK.

As classes deste módulo são ``Protocol``: servem apenas para anotar tipos
e validar a interface esperada por ferramentas como mypy. Elas não
fornecem implementação em tempo de execução, por isso seus métodos usam
``...`` como corpo.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx


class SyncHTTPClient(Protocol):
    """Interface mínima esperada de um cliente HTTP síncrono.

    Destinado a anotações de tipo quando o código consumidor precisa
    chamar métodos HTTP comuns sem depender da classe concreta retornada
    por ``build_http_client``. Os métodos declaram apenas assinaturas
    porque a implementação pertence ao cliente concreto.
    """

    def get(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Envia ``GET`` e retorna a resposta HTTP."""
        ...

    def post(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Envia ``POST`` e retorna a resposta HTTP."""
        ...

    def put(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Envia ``PUT`` e retorna a resposta HTTP."""
        ...

    def patch(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Envia ``PATCH`` e retorna a resposta HTTP."""
        ...

    def delete(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Envia ``DELETE`` e retorna a resposta HTTP."""
        ...

    def close(self) -> None:
        """Libera recursos associados ao cliente."""
        ...


class AsyncHTTPClientProtocol(Protocol):
    """Interface mínima esperada de um cliente HTTP assíncrono.

    Destinado a anotações de tipo quando o código consumidor precisa
    chamar métodos HTTP com ``await`` sem depender da classe concreta
    retornada por ``build_async_http_client``. Os métodos declaram apenas
    assinaturas porque a implementação pertence ao cliente concreto.
    """

    async def get(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Envia ``GET`` e retorna a resposta HTTP."""
        ...

    async def post(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Envia ``POST`` e retorna a resposta HTTP."""
        ...

    async def put(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Envia ``PUT`` e retorna a resposta HTTP."""
        ...

    async def patch(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Envia ``PATCH`` e retorna a resposta HTTP."""
        ...

    async def delete(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Envia ``DELETE`` e retorna a resposta HTTP."""
        ...

    async def aclose(self) -> None:
        """Libera recursos associados ao cliente."""
        ...
