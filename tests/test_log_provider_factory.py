from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.log_providers.factory import build_log_providers
from sme_sidecar_sdk.log_providers.rabbitmq import RabbitMQLogProvider


def test_no_provider_is_created_without_queue() -> None:
    assert build_log_providers(Settings()) == []


def test_rabbitmq_provider_is_created_when_queue_is_configured() -> None:
    providers = build_log_providers(
        Settings(SME_LOG_RABBITMQ_QUEUE="logs.pedagogico")
    )

    assert len(providers) == 1
    assert isinstance(providers[0], RabbitMQLogProvider)
