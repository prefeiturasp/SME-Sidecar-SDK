"""Carregador de configuração do SME Sidecar SDK.

Este módulo expõe :class:`Settings`, um modelo ``pydantic-settings`` que
carrega a configuração do SDK a partir de variáveis de ambiente
prefixadas com ``SME_``.

Cobre os recursos de resiliência e observabilidade, incluindo timeout,
retry, circuit breaker, logging estruturado, correlação e tracing
distribuído.

Example:
    >>> from sme_sidecar_sdk.config import Settings
    >>> settings = Settings()  # lê variáveis SME_*
    >>> settings.timeout_seconds
    10.0
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["json", "console"]
Broker = Literal["rabbitmq"]


def _aliases(env_name: str, field_name: str) -> AliasChoices:
    """Retorna ``AliasChoices`` aceitando env var ou atributo Python."""
    return AliasChoices(env_name, field_name)


class Settings(BaseSettings):
    """Configuração do runtime carregada a partir das variáveis ``SME_*``.

    Attributes:
        enabled: Chave geral que liga/desliga o runtime do SDK.
        service_name: Nome lógico do serviço consumidor.
        service_version: Versão do serviço consumidor.
        environment: Ambiente de deploy (``dev``, ``qa``, ``prod``).
        timeout_enabled: Habilita o wrapper de timeout padronizado
            para HTTP.
        timeout_seconds: Timeout total aplicado a chamadas HTTP de
            saída.
        retry_enabled: Habilita o decorador de retry baseado em
            Tenacity.
        retry_attempts: Número máximo de tentativas (incluindo a
            primeira chamada).
        retry_backoff_min: Limite inferior (em segundos) do backoff
            exponencial.
        retry_backoff_max: Limite superior (em segundos) do backoff
            exponencial.
        circuit_breaker_enabled: Habilita o circuit breaker baseado em
            PyBreaker.
        circuit_breaker_fail_max: Quantidade de falhas tolerada antes
            da abertura do circuito.
        circuit_breaker_reset_timeout: Tempo (em segundos) que o
            circuito permanece aberto antes de transitar para o estado
            meio-aberto.
        logging_enabled: Habilita a padronização de logs.
        log_level: Nível mínimo emitido pelos loggers.
        log_format: Formato de saída, JSON ou console.
        broker: Broker usado pelo provider de fila de logs.
        broker_url: URL de conexão compartilhada com o broker.
        log_queue: Fila que ativa o provider de fila de logs.
        log_queue_buffer_size: Limite do buffer local não bloqueante.
        log_queue_socket_timeout: Timeout de conexão com o broker.
        log_queue_poll_interval: Intervalo de consulta ao buffer de logs.
        log_queue_shutdown_timeout: Tempo máximo de espera no encerramento.
        correlation_id_header: Header usado para propagar o request ID.
        otel_enabled: Habilita tracing distribuído.
        otel_exporter_otlp_endpoint: Endpoint OTLP gRPC do collector ou APM.
        otel_exporter_otlp_headers: Headers de autenticação do exporter.
        otel_exporter_otlp_insecure: Desabilita TLS no transporte OTLP.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    enabled: bool = Field(
        default=True,
        validation_alias=_aliases("SME_SDK_ENABLED", "enabled"),
    )
    service_name: str = Field(
        default="unnamed-service",
        validation_alias=_aliases("SME_SERVICE_NAME", "service_name"),
    )
    environment: str = Field(
        default="dev",
        validation_alias=_aliases("SME_ENVIRONMENT", "environment"),
    )
    service_version: str = Field(
        default="unknown",
        validation_alias=_aliases(
            "SME_SERVICE_VERSION",
            "service_version",
        ),
    )

    timeout_enabled: bool = Field(
        default=True,
        validation_alias=_aliases("SME_TIMEOUT_ENABLED", "timeout_enabled"),
    )
    timeout_seconds: float = Field(
        default=10.0,
        ge=0.1,
        validation_alias=_aliases("SME_TIMEOUT_SECONDS", "timeout_seconds"),
    )

    retry_enabled: bool = Field(
        default=True,
        validation_alias=_aliases("SME_RETRY_ENABLED", "retry_enabled"),
    )
    retry_attempts: int = Field(
        default=3,
        ge=1,
        validation_alias=_aliases("SME_RETRY_ATTEMPTS", "retry_attempts"),
    )
    retry_backoff_min: float = Field(
        default=0.5,
        ge=0.0,
        validation_alias=_aliases(
            "SME_RETRY_BACKOFF_MIN", "retry_backoff_min"
        ),
    )
    retry_backoff_max: float = Field(
        default=5.0,
        ge=0.0,
        validation_alias=_aliases(
            "SME_RETRY_BACKOFF_MAX", "retry_backoff_max"
        ),
    )

    circuit_breaker_enabled: bool = Field(
        default=True,
        validation_alias=_aliases(
            "SME_CIRCUIT_BREAKER_ENABLED",
            "circuit_breaker_enabled",
        ),
    )
    circuit_breaker_fail_max: int = Field(
        default=5,
        ge=1,
        validation_alias=_aliases(
            "SME_CIRCUIT_BREAKER_FAIL_MAX",
            "circuit_breaker_fail_max",
        ),
    )
    circuit_breaker_reset_timeout: float = Field(
        default=30.0,
        ge=1.0,
        validation_alias=_aliases(
            "SME_CIRCUIT_BREAKER_RESET_TIMEOUT",
            "circuit_breaker_reset_timeout",
        ),
    )

    logging_enabled: bool = Field(
        default=True,
        validation_alias=_aliases(
            "SME_LOGGING_ENABLED",
            "logging_enabled",
        ),
    )
    log_level: LogLevel = Field(
        default="ERROR",
        validation_alias=_aliases("SME_LOG_LEVEL", "log_level"),
    )
    log_format: LogFormat = Field(
        default="json",
        validation_alias=_aliases("SME_LOG_FORMAT", "log_format"),
    )
    broker: Broker = Field(
        default="rabbitmq",
        validation_alias=_aliases("SME_BROKER", "broker"),
    )
    broker_url: str = Field(
        default="amqp://guest:guest@localhost:5672/%2F",
        min_length=1,
        validation_alias=_aliases("SME_BROKER_URL", "broker_url"),
    )
    log_queue: str = Field(
        default="",
        validation_alias=_aliases("SME_LOG_QUEUE", "log_queue"),
    )
    log_queue_buffer_size: int = Field(
        default=10_000,
        ge=1,
        validation_alias=_aliases(
            "SME_LOG_QUEUE_BUFFER_SIZE",
            "log_queue_buffer_size",
        ),
    )
    log_queue_socket_timeout: float = Field(
        default=2.0,
        ge=0.1,
        validation_alias=_aliases(
            "SME_LOG_QUEUE_SOCKET_TIMEOUT",
            "log_queue_socket_timeout",
        ),
    )
    log_queue_poll_interval: float = Field(
        default=0.25,
        ge=0.01,
        validation_alias=_aliases(
            "SME_LOG_QUEUE_POLL_INTERVAL",
            "log_queue_poll_interval",
        ),
    )
    log_queue_shutdown_timeout: float = Field(
        default=2.0,
        ge=0.0,
        validation_alias=_aliases(
            "SME_LOG_QUEUE_SHUTDOWN_TIMEOUT",
            "log_queue_shutdown_timeout",
        ),
    )
    correlation_id_header: str = Field(
        default="X-Request-ID",
        min_length=1,
        validation_alias=_aliases(
            "SME_CORRELATION_ID_HEADER",
            "correlation_id_header",
        ),
    )

    otel_enabled: bool = Field(
        default=False,
        validation_alias=_aliases("SME_OTEL_ENABLED", "otel_enabled"),
    )
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317",
        min_length=1,
        validation_alias=_aliases(
            "SME_OTEL_EXPORTER_OTLP_ENDPOINT",
            "otel_exporter_otlp_endpoint",
        ),
    )
    otel_exporter_otlp_headers: str = Field(
        default="",
        validation_alias=_aliases(
            "SME_OTEL_EXPORTER_OTLP_HEADERS",
            "otel_exporter_otlp_headers",
        ),
    )
    otel_exporter_otlp_insecure: bool = Field(
        default=True,
        validation_alias=_aliases(
            "SME_OTEL_EXPORTER_OTLP_INSECURE",
            "otel_exporter_otlp_insecure",
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna uma instância de :class:`Settings` cacheada por processo.

    A primeira chamada instancia :class:`Settings`, que lê o ambiente.
    Chamadas subsequentes devolvem o mesmo objeto, evitando releitura.

    Returns:
        Settings: Instância de configuração cacheada.
    """
    return Settings()


def reset_settings_cache() -> None:
    """Limpa o cache da instância de :class:`Settings`.

    Útil em testes quando as variáveis de ambiente mudam entre casos.
    """
    get_settings.cache_clear()
