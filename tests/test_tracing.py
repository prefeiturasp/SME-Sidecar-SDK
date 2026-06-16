"""Testes dos primitivos de tracing distribuído."""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.observability import tracing
from sme_sidecar_sdk.observability.tracing import (
    _parse_headers,
    extract_trace_context,
    inject_trace_context,
    use_trace_context,
)


def test_parse_otlp_headers_supports_elastic_authorization() -> None:
    headers = _parse_headers("Authorization=Bearer%20secret,x-team=sme")
    assert headers == (
        ("authorization", "Bearer secret"),
        ("x-team", "sme"),
    )


def test_trace_context_round_trip() -> None:
    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    carrier: dict[str, str] = {}

    with tracer.start_as_current_span("origem"):
        inject_trace_context(carrier)

    assert "traceparent" in carrier
    extracted = extract_trace_context(carrier)
    with use_trace_context(carrier):
        current = trace.get_current_span().get_span_context()

    extracted_span = trace.get_current_span(extracted).get_span_context()
    assert current.trace_id == extracted_span.trace_id


def test_configure_tracing_builds_exporter_and_instruments_httpx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter_arguments: dict[str, object] = {}
    instrument_arguments: dict[str, object] = {}
    django_instrument_arguments: dict[str, object] = {}

    def build_exporter(**kwargs: object) -> InMemorySpanExporter:
        exporter_arguments.update(kwargs)
        return InMemorySpanExporter()

    def instrument(_self: object, **kwargs: object) -> None:
        instrument_arguments.update(kwargs)

    monkeypatch.setattr(tracing, "OTLPSpanExporter", build_exporter)
    monkeypatch.setattr(
        HTTPXClientInstrumentor,
        "instrument",
        instrument,
    )
    monkeypatch.setattr(tracing, "_PROVIDER", None)
    monkeypatch.setattr(tracing, "_HTTPX_INSTRUMENTED", False)
    monkeypatch.setattr(tracing, "_DJANGO_INSTRUMENTED", False)

    class FakeDjangoInstrumentor:
        def instrument(self, **kwargs: object) -> None:
            django_instrument_arguments.update(kwargs)

    class FakeDjangoModule:
        DjangoInstrumentor = FakeDjangoInstrumentor

    def import_module(name: str) -> object:
        assert name == "opentelemetry.instrumentation.django"
        return FakeDjangoModule

    monkeypatch.setattr(tracing, "import_module", import_module)

    provider = tracing.configure_tracing(
        Settings(
            SME_OTEL_ENABLED=True,
            SME_OTEL_EXPORTER_OTLP_ENDPOINT="https://apm.example:8200",
            SME_OTEL_EXPORTER_OTLP_HEADERS=("Authorization=Bearer%20secret"),
            SME_OTEL_EXPORTER_OTLP_INSECURE=False,
        )
    )

    assert isinstance(provider, TracerProvider)
    assert provider.resource.attributes["deployment.environment"] == "dev"
    assert provider.resource.attributes["deployment.environment.name"] == "dev"
    assert exporter_arguments == {
        "endpoint": "https://apm.example:8200",
        "headers": (("authorization", "Bearer secret"),),
        "insecure": False,
    }
    assert instrument_arguments["tracer_provider"] is provider
    assert django_instrument_arguments["tracer_provider"] is provider


def test_configure_tracing_skips_django_when_dependency_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tracing, "_PROVIDER", None)
    monkeypatch.setattr(tracing, "_HTTPX_INSTRUMENTED", False)
    monkeypatch.setattr(tracing, "_DJANGO_INSTRUMENTED", False)
    monkeypatch.setattr(
        tracing,
        "OTLPSpanExporter",
        lambda **_: InMemorySpanExporter(),
    )
    monkeypatch.setattr(
        HTTPXClientInstrumentor,
        "instrument",
        lambda _self, **__: None,
    )

    def import_module(_: str) -> object:
        raise ModuleNotFoundError(name="django")

    monkeypatch.setattr(tracing, "import_module", import_module)

    provider = tracing.configure_tracing(Settings(SME_OTEL_ENABLED=True))

    assert isinstance(provider, TracerProvider)
    assert tracing._DJANGO_INSTRUMENTED is False
