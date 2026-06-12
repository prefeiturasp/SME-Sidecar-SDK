"""Testes da padronização de logs."""

from __future__ import annotations

import json
import logging
from typing import cast
from unittest.mock import patch

import pytest

from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.observability.context import correlation_context
from sme_sidecar_sdk.observability.logging import (
    configure_logging,
    get_logger,
    shutdown_logging,
)


class _CapturingProvider:
    def __init__(self) -> None:
        self.payloads: list[str] = []
        self.shutdown_called = False

    def build_handler(
        self,
        formatter: logging.Formatter,
    ) -> logging.Handler:
        provider = self

        class CapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                provider.payloads.append(self.format(record))

        handler = CapturingHandler()
        handler.setFormatter(formatter)
        return handler

    def shutdown(self) -> None:
        self.shutdown_called = True


def _last_payload(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines
    return cast(dict[str, object], json.loads(lines[-1]))


def test_structured_log_contains_standard_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(
        Settings(
            SME_SERVICE_NAME="pedagogico-ms",
            SME_ENVIRONMENT="qa",
            SME_LOG_LEVEL="INFO",
        )
    )
    with correlation_context(correlation_id="request-42"):
        get_logger("teste").info("consulta_concluida", status_code=200)

    payload = _last_payload(capsys)
    assert payload["event"] == "consulta_concluida"
    assert payload["service"] == "pedagogico-ms"
    assert payload["environment"] == "qa"
    assert payload["request_id"] == "request-42"
    assert payload["status_code"] == 200
    assert payload["level"] == "info"
    assert "timestamp" in payload


def test_standard_library_logs_use_same_json_format(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(
        Settings(
            SME_SERVICE_NAME="servico",
            SME_LOG_LEVEL="WARNING",
        )
    )
    logging.getLogger("legado").warning("falha temporaria")

    payload = _last_payload(capsys)
    assert payload["event"] == "falha temporaria"
    assert payload["service"] == "servico"
    assert payload["level"] == "warning"


def test_external_provider_receives_structured_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    provider = _CapturingProvider()
    with patch(
        (
            "sme_sidecar_sdk.observability.logging.configuration."
            "build_log_providers"
        ),
        return_value=[provider],
    ):
        configure_logging(
            Settings(
                SME_SERVICE_NAME="pedagogico-ms",
                SME_ENVIRONMENT="qa",
                SME_LOG_LEVEL="ERROR",
                SME_LOG_FORMAT="console",
            )
        )
        with correlation_context(correlation_id="request-42"):
            get_logger("teste").error("consulta_falhou", status_code=500)

    payload = json.loads(provider.payloads[-1])
    assert payload["event"] == "consulta_falhou"
    assert payload["service"] == "pedagogico-ms"
    assert payload["environment"] == "qa"
    assert payload["request_id"] == "request-42"
    assert payload["status_code"] == 500

    shutdown_logging()
    assert provider.shutdown_called is True
    capsys.readouterr()


def test_error_level_filters_warning_from_standard_library(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(Settings(SME_LOG_LEVEL="ERROR"))

    logging.getLogger("legado").warning("nao deve aparecer")

    assert capsys.readouterr().out == ""
