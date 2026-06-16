from __future__ import annotations

import logging
import queue
from unittest.mock import MagicMock, patch

from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.observability.logging.providers.rabbitmq import (
    RabbitMQLogProvider,
    _RabbitMQHandler,
)


def _settings() -> Settings:
    return Settings(
        SME_LOG_LEVEL="ERROR",
        SME_LOG_QUEUE="logs.pedagogico",
        SME_LOG_QUEUE_BUFFER_SIZE=2,
        SME_LOG_QUEUE_POLL_INTERVAL=0.01,
        SME_LOG_QUEUE_SHUTDOWN_TIMEOUT=0.1,
    )


def test_handler_does_not_block_when_buffer_is_full() -> None:
    messages: queue.Queue[str | object] = queue.Queue(maxsize=1)
    messages.put_nowait("already-full")
    handler = _RabbitMQHandler(messages, logging.ERROR)

    handler.emit(logging.LogRecord("app", logging.ERROR, "", 1, "x", (), None))

    assert handler.dropped_messages == 1


def test_handler_ignores_pika_internal_logs() -> None:
    messages: queue.Queue[str | object] = queue.Queue()
    handler = _RabbitMQHandler(messages, logging.ERROR)

    handler.emit(
        logging.LogRecord(
            "pika.connection",
            logging.ERROR,
            "",
            1,
            "x",
            (),
            None,
        )
    )

    assert messages.empty()


def test_provider_declares_queue_and_publishes_persistent_json() -> None:
    connection = MagicMock()
    connection.is_closed = False
    channel = connection.channel.return_value

    with patch(
        (
            "sme_sidecar_sdk.observability.logging.providers.rabbitmq."
            "pika.BlockingConnection"
        ),
        return_value=connection,
    ):
        provider = RabbitMQLogProvider(_settings())
        assert provider._publish('{"event":"failure"}') is True

    channel.queue_declare.assert_called_once_with(
        queue="logs.pedagogico",
        durable=True,
    )
    publish = channel.basic_publish.call_args
    assert publish.kwargs["exchange"] == ""
    assert publish.kwargs["routing_key"] == "logs.pedagogico"
    assert publish.kwargs["body"] == '{"event":"failure"}'
    assert publish.kwargs["properties"].content_type == "application/json"
    assert publish.kwargs["properties"].delivery_mode == 2


def test_provider_swallows_connection_failure() -> None:
    with patch(
        (
            "sme_sidecar_sdk.observability.logging.providers.rabbitmq."
            "pika.BlockingConnection"
        ),
        side_effect=ConnectionError("rabbit unavailable"),
    ):
        provider = RabbitMQLogProvider(_settings())

        assert provider._publish('{"event":"failure"}') is False


def test_shutdown_stops_background_thread() -> None:
    provider = RabbitMQLogProvider(_settings())
    provider.build_handler(logging.Formatter("%(message)s"))

    provider.shutdown()

    assert provider._thread is not None
    assert not provider._thread.is_alive()
