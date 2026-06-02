"""Carregador de configuração do SME Sidecar SDK.

Este módulo expõe :class:`Settings`, um modelo ``pydantic-settings`` que
carrega a configuração do SDK a partir de variáveis de ambiente
prefixadas com ``SME_``.

Cobre o ajuste fino dos primitivos de resiliência: timeout, retry e
circuit breaker.

Example:
    >>> from sme_sidecar_sdk.config import Settings
    >>> settings = Settings()  # lê variáveis SME_*
    >>> settings.timeout_seconds
    10.0
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _aliases(env_name: str, field_name: str) -> AliasChoices:
    """Retorna ``AliasChoices`` aceitando env var ou atributo Python."""
    return AliasChoices(env_name, field_name)


class Settings(BaseSettings):
    """Configuração do runtime carregada a partir das variáveis ``SME_*``.

    Attributes:
        enabled: Chave geral que liga/desliga o runtime do SDK.
        service_name: Nome lógico do serviço consumidor.
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
