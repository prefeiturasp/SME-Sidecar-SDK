"""Exceções públicas do SME Sidecar SDK.

Este módulo expõe as classes de exceção que os consumidores precisam
capturar ao usar os primitivos de resiliência. As implementações são
reexportadas das bibliotecas subjacentes (httpx, pybreaker), de modo
que o consumidor **não precise importar essas bibliotecas
diretamente**.

Tabela de mapeamento:

+-----------------------+-------------------------------------+
| Exceção pública       | Origem interna                      |
+=======================+=====================================+
| ``RequestTimeoutError`` | ``httpx.TimeoutException``        |
+-----------------------+-------------------------------------+
| ``UpstreamHTTPError``   | ``httpx.HTTPStatusError``         |
+-----------------------+-------------------------------------+
| ``CircuitOpenError``    | ``pybreaker.CircuitBreakerError`` |
+-----------------------+-------------------------------------+

Como são aliases diretos das classes originais, ``isinstance`` e
``except`` continuam funcionando para qualquer código que ainda use os
tipos internos — a SDK apenas oferece nomes públicos estáveis.

Example:
    >>> from sme_sidecar_sdk.exceptions import (
    ...     CircuitOpenError,
    ...     RequestTimeoutError,
    ...     UpstreamHTTPError,
    ... )
    >>> try:
    ...     ...
    ... except CircuitOpenError:
    ...     ...
"""

from __future__ import annotations

from httpx import HTTPStatusError as UpstreamHTTPError
from httpx import TimeoutException as RequestTimeoutError
from pybreaker import CircuitBreakerError as CircuitOpenError

__all__ = [
    "CircuitOpenError",
    "RequestTimeoutError",
    "UpstreamHTTPError",
]
