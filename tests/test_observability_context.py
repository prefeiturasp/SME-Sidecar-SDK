"""Testes do contexto unificado de requisição."""

from __future__ import annotations

from opentelemetry import trace

from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.observability.context import (
    get_correlation_id,
    request_context,
)


def test_request_context_uses_configured_header_and_restores_state() -> None:
    settings = Settings(SME_CORRELATION_ID_HEADER="X-Correlation-ID")

    with request_context(
        {"x-correlation-id": "correlation-123"},
        settings,
    ) as current:
        assert current.request_id == "correlation-123"
        assert get_correlation_id() == "correlation-123"

    assert get_correlation_id() is None


def test_request_context_extracts_mixed_case_traceparent() -> None:
    trace_id = "c7fd506fb2c1636a89a8e98fbccd41d0"
    parent_span_id = "45307b965c06e91f"

    with request_context(
        {"Traceparent": (f"00-{trace_id}-{parent_span_id}-01")}
    ):
        span_context = trace.get_current_span().get_span_context()

        assert span_context.is_valid
        assert span_context.is_remote
        assert f"{span_context.trace_id:032x}" == trace_id
        assert f"{span_context.span_id:016x}" == parent_span_id
