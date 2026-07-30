"""Cliente HTTP compartilhado com resiliência e observabilidade."""

from ._types import AsyncHTTPClientProtocol, SyncHTTPClient
from .client import (
    AsyncHTTPClient,
    HTTPClient,
    build_async_http_client,
    build_http_client,
)

__all__ = [
    "AsyncHTTPClient",
    "AsyncHTTPClientProtocol",
    "HTTPClient",
    "SyncHTTPClient",
    "build_async_http_client",
    "build_http_client",
]
