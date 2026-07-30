from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import patch

import pytest

from sme_sidecar_sdk.integrations.django import ObservabilityMiddleware
from sme_sidecar_sdk.observability.context import get_correlation_id


@dataclass
class FakeRequest:
    headers: dict[str, str]
    method: str = "GET"
    path: str = "/health/"
    request_id: str = ""


@dataclass
class FakeResponse:
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)

    def __setitem__(self, key: str, value: str) -> None:
        self.headers[key] = value


def test_middleware_reuses_request_id_and_clears_context() -> None:
    seen_request_ids: list[str | None] = []

    def get_response(request: FakeRequest) -> FakeResponse:
        seen_request_ids.append(get_correlation_id())
        assert request.request_id == "request-123"
        return FakeResponse()

    middleware = ObservabilityMiddleware(get_response)
    response = middleware(FakeRequest(headers={"X-Request-ID": "request-123"}))

    assert response.headers["X-Request-ID"] == "request-123"
    assert seen_request_ids == ["request-123"]
    assert get_correlation_id() is None


def test_middleware_generates_request_id() -> None:
    middleware: ObservabilityMiddleware[FakeRequest, FakeResponse] = (
        ObservabilityMiddleware(lambda _: FakeResponse())
    )

    response = middleware(FakeRequest(headers={}))

    assert response.headers["X-Request-ID"]


def test_middleware_logs_completed_request() -> None:
    with (
        patch("sme_sidecar_sdk.integrations.django.log.info") as log_info,
        patch(
            "sme_sidecar_sdk.integrations.django.time.monotonic",
            side_effect=[10.0, 10.125],
        ),
    ):
        middleware: ObservabilityMiddleware[FakeRequest, FakeResponse] = (
            ObservabilityMiddleware(lambda _: FakeResponse(status_code=204))
        )
        middleware(FakeRequest(headers={}, method="POST", path="/turmas/"))

    log_info.assert_called_once_with(
        "http_request_completed",
        http_method="POST",
        http_path="/turmas/",
        http_status_code=204,
        http_duration_ms=125.0,
    )


def test_middleware_logs_500_and_restores_context_on_exception() -> None:
    def raise_error(_: FakeRequest) -> FakeResponse:
        raise RuntimeError("falha")

    with patch("sme_sidecar_sdk.integrations.django.log.error") as log_error:
        middleware = ObservabilityMiddleware(raise_error)

        with pytest.raises(RuntimeError, match="falha"):
            middleware(
                FakeRequest(headers={"X-Request-ID": "request-with-error"})
            )

    assert get_correlation_id() is None
    assert log_error.call_args.kwargs["http_status_code"] == 500


def test_middleware_logs_500_response_as_error() -> None:
    with patch("sme_sidecar_sdk.integrations.django.log.error") as log_error:
        middleware: ObservabilityMiddleware[FakeRequest, FakeResponse] = (
            ObservabilityMiddleware(lambda _: FakeResponse(status_code=503))
        )
        response = middleware(FakeRequest(headers={}))

    assert response.status_code == 503
    assert log_error.call_args.kwargs["http_status_code"] == 503
