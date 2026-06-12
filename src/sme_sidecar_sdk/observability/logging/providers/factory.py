"""Factory dos providers de transporte de logs."""

from __future__ import annotations

from ....config import Settings
from .base import LogProvider
from .rabbitmq import RabbitMQLogProvider


def build_log_providers(settings: Settings) -> list[LogProvider]:
    """Constrói os providers habilitados pela configuração.

    Args:
        settings: Configuração efetiva do SDK.

    Returns:
        Providers habilitados para transporte de logs.
    """
    providers: list[LogProvider] = []
    if settings.log_rabbitmq_queue:
        providers.append(RabbitMQLogProvider(settings))
    return providers
