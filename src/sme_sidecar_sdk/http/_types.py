"""Protocolos de tipagem para clientes HTTP da SDK."""

from __future__ import annotations

from typing import Any, Protocol

import httpx


class SyncHTTPClient(Protocol):
    """Contrato público de um cliente HTTP síncrono da SDK."""

    def get(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Executa uma requisição ``GET``."""
        ...

    def post(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Executa uma requisição ``POST``."""
        ...

    def put(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Executa uma requisição ``PUT``."""
        ...

    def patch(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Executa uma requisição ``PATCH``."""
        ...

    def delete(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        """Executa uma requisição ``DELETE``."""
        ...

    def close(self) -> None:
        """Fecha conexões mantidas pelo cliente."""
        ...


class AsyncHTTPClientProtocol(Protocol):
    """Contrato público de um cliente HTTP assíncrono da SDK."""

    async def get(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa uma requisição ``GET``."""
        ...

    async def post(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa uma requisição ``POST``."""
        ...

    async def put(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa uma requisição ``PUT``."""
        ...

    async def patch(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa uma requisição ``PATCH``."""
        ...

    async def delete(
        self,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa uma requisição ``DELETE``."""
        ...

    async def aclose(self) -> None:
        """Fecha conexões mantidas pelo cliente assíncrono."""
        ...
