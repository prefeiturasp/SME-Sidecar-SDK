"""Integrações opcionais com frameworks de aplicação."""

from .asgi import ASGIObservabilityMiddleware, instrument_asgi_application

__all__ = [
    "ASGIObservabilityMiddleware",
    "instrument_asgi_application",
]
