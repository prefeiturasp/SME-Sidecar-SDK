"""Propagação de identificadores de correlação por contexto de execução."""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token

_CORRELATION_ID: ContextVar[str | None] = ContextVar(
    "sme_correlation_id",
    default=None,
)


def get_correlation_id() -> str | None:
    """Retorna o identificador associado ao contexto atual.

    Returns:
        Identificador de correlação ativo ou ``None`` quando não há contexto.
    """
    return _CORRELATION_ID.get()


def set_correlation_id(value: str) -> Token[str | None]:
    """Associa um identificador ao contexto atual.

    Args:
        value: Identificador de correlação que será ativado.

    Returns:
        Token que permite restaurar o valor anterior do contexto.
    """
    return _CORRELATION_ID.set(value)


def reset_correlation_id(token: Token[str | None]) -> None:
    """Restaura o contexto capturado pelo token informado.

    Args:
        token: Token retornado por :func:`set_correlation_id`.

    Raises:
        ValueError: Se o token pertencer a outro contexto.
        RuntimeError: Se o token já tiver sido utilizado.
    """
    _CORRELATION_ID.reset(token)


def new_correlation_id() -> str:
    """Gera um identificador UUID4 para uma nova cadeia de requisições.

    Returns:
        UUID4 no formato textual.
    """
    return str(uuid.uuid4())


def correlation_id_from_headers(
    headers: Mapping[str, str],
    header_name: str = "X-Request-ID",
) -> str | None:
    """Extrai o identificador de headers sem diferenciar maiúsculas.

    Args:
        headers: Headers nos quais o identificador será procurado.
        header_name: Nome do header de correlação.

    Returns:
        Valor normalizado do header ou ``None`` quando ausente ou vazio.
    """
    expected = header_name.casefold()
    for name, value in headers.items():
        if name.casefold() == expected and value.strip():
            return value.strip()
    return None


@contextmanager
def correlation_context(
    headers: Mapping[str, str] | None = None,
    *,
    header_name: str = "X-Request-ID",
    correlation_id: str | None = None,
) -> Iterator[str]:
    """Cria um escopo de correlação e restaura o contexto ao encerrá-lo.

    A precedência é: valor explícito, header recebido e novo UUID4.

    Args:
        headers: Headers usados para obter o identificador de correlação.
        header_name: Nome do header de correlação.
        correlation_id: Identificador explícito com maior precedência.

    Yields:
        Identificador ativo durante o escopo.
    """
    value = (
        correlation_id
        or correlation_id_from_headers(headers or {}, header_name)
        or new_correlation_id()
    )
    token = set_correlation_id(value)
    try:
        yield value
    finally:
        reset_correlation_id(token)
