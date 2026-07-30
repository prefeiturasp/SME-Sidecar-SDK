"""Testes dos identificadores de correlação."""

from __future__ import annotations

from sme_sidecar_sdk.observability.context import (
    correlation_context,
    correlation_id_from_headers,
    get_correlation_id,
    new_correlation_id,
)


def test_extracts_header_case_insensitively() -> None:
    headers = {"x-request-id": " abc-123 "}
    assert correlation_id_from_headers(headers) == "abc-123"


def test_context_restores_previous_value() -> None:
    assert get_correlation_id() is None
    with correlation_context(correlation_id="outer"):
        assert get_correlation_id() == "outer"
        with correlation_context(correlation_id="inner"):
            assert get_correlation_id() == "inner"
        assert get_correlation_id() == "outer"
    assert get_correlation_id() is None


def test_new_ids_are_unique() -> None:
    assert len({new_correlation_id() for _ in range(20)}) == 20
