"""Provider assíncrono de logs para RabbitMQ."""

from __future__ import annotations

import logging
import queue
import threading
from contextlib import suppress
from typing import Any

import pika

from ..config import Settings

_STOP = object()


class _RabbitMQHandler(logging.Handler):
    """Enfileira logs sem bloquear a thread da aplicação."""

    def __init__(
        self,
        messages: queue.Queue[str | object],
        level: int,
    ) -> None:
        """Inicializa o handler com o buffer compartilhado.

        Args:
            messages: Fila local que recebe os registros formatados.
            level: Nível mínimo aceito pelo handler.
        """
        super().__init__(level)
        self._messages = messages
        self.dropped_messages = 0

    def emit(self, record: logging.LogRecord) -> None:
        """Formata e adiciona um registro ao buffer local."""
        if record.name.startswith(("pika", __name__)):
            return
        try:
            self._messages.put_nowait(self.format(record))
        except queue.Full:
            self.dropped_messages += 1
        except Exception:
            self.handleError(record)


class RabbitMQLogProvider:
    """Publica logs em RabbitMQ por uma thread de background."""

    def __init__(self, settings: Settings) -> None:
        """Inicializa o provider sem abrir conexão com o broker.

        Args:
            settings: Configuração da conexão e do buffer de mensagens.
        """
        self._settings = settings
        self._messages: queue.Queue[str | object] = queue.Queue(
            maxsize=settings.log_rabbitmq_buffer_size
        )
        self._handler: _RabbitMQHandler | None = None
        self._thread: threading.Thread | None = None
        self._connection: Any = None
        self._channel: Any = None
        self._stopping = threading.Event()

    def build_handler(
        self,
        formatter: logging.Formatter,
    ) -> logging.Handler:
        """Cria o handler e inicia o publicador em background.

        Args:
            formatter: Formatador JSON aplicado aos registros.

        Returns:
            Handler que envia registros ao buffer local.
        """
        handler = _RabbitMQHandler(
            self._messages,
            logging.getLevelNamesMapping()[self._settings.log_level],
        )
        handler.setFormatter(formatter)
        self._handler = handler
        self._thread = threading.Thread(
            target=self._run,
            name="sme-rabbitmq-log-provider",
            daemon=True,
        )
        self._thread.start()
        return handler

    def _connect(self) -> None:
        """Abre a conexão e declara a fila durável."""
        parameters = pika.URLParameters(self._settings.rabbitmq_url)
        parameters.connection_attempts = 1
        parameters.socket_timeout = self._settings.log_rabbitmq_socket_timeout
        parameters.blocked_connection_timeout = (
            self._settings.log_rabbitmq_socket_timeout
        )
        self._connection = pika.BlockingConnection(parameters)
        self._channel = self._connection.channel()
        self._channel.queue_declare(
            queue=self._settings.log_rabbitmq_queue,
            durable=True,
        )

    def _ensure_connected(self) -> bool:
        """Garante conexão ativa sem propagar falhas à aplicação."""
        try:
            if self._connection is None or self._connection.is_closed:
                self._connect()
            return True
        except Exception:
            self._discard_connection()
            return False

    def _publish(self, body: str) -> bool:
        """Publica uma mensagem e informa se houve sucesso."""
        if not self._ensure_connected():
            return False
        try:
            self._channel.basic_publish(
                exchange="",
                routing_key=self._settings.log_rabbitmq_queue,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent,
                    content_type="application/json",
                ),
            )
            return True
        except Exception:
            self._discard_connection()
            return False

    def _run(self) -> None:
        """Consome o buffer local até o encerramento do provider."""
        while not self._stopping.is_set():
            try:
                message = self._messages.get(
                    timeout=self._settings.log_rabbitmq_poll_interval
                )
            except queue.Empty:
                continue
            try:
                if message is _STOP:
                    return
                self._publish(str(message))
            finally:
                self._messages.task_done()

    def _discard_connection(self) -> None:
        """Descarta conexão e canal para uma tentativa futura."""
        self._channel = None
        self._connection = None

    def shutdown(self) -> None:
        """Encerra a thread e fecha a conexão sem bloquear indefinidamente."""
        self._stopping.set()
        with suppress(queue.Full):
            self._messages.put_nowait(_STOP)
        if self._thread is not None:
            self._thread.join(
                timeout=self._settings.log_rabbitmq_shutdown_timeout
            )
        try:
            if self._connection is not None and self._connection.is_open:
                self._connection.close()
        except Exception:
            pass
        self._discard_connection()
