"""Testes do contexto unificado de requisição."""

from __future__ import annotations

from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.correlation import get_correlation_id
from sme_sidecar_sdk.observability import request_context


def test_request_context_uses_configured_header_and_restores_state() -> None:
    settings = Settings(SME_CORRELATION_ID_HEADER="X-Correlation-ID")

    with request_context(
        {"x-correlation-id": "correlation-123"},
        settings,
    ) as current:
        assert current.request_id == "correlation-123"
        assert get_correlation_id() == "correlation-123"

    assert get_correlation_id() is None
