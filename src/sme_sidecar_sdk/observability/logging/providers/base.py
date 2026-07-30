"""Contrato dos providers de transporte de logs."""

from __future__ import annotations

import logging
from typing import Protocol


class LogProvider(Protocol):
    """Contrato para providers conectados ao logging padrão."""

    def build_handler(
        self,
        formatter: logging.Formatter,
    ) -> logging.Handler:
        """Constrói o handler usado pelo logging padrão.

        Args:
            formatter: Formatador aplicado aos registros emitidos.

        Returns:
            Handler configurado para transportar os registros.
        """
        ...

    def shutdown(self) -> None:
        """Libera os recursos mantidos pelo provider."""
        ...
