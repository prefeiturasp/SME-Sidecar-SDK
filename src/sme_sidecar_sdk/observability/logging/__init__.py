"""Feature de logs estruturados do domínio de observabilidade."""

from .configuration import configure_logging, get_logger, shutdown_logging

__all__ = ["configure_logging", "get_logger", "shutdown_logging"]
