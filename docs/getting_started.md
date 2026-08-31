# Getting Started

Este guia mostra o caminho mínimo para instalar a SDK, integrar com Django
e começar a usar os recursos principais.

## Instalação

Escolha uma versão publicada em
[SME-Sidecar-SDK releases](https://github.com/prefeiturasp/SME-Sidecar-SDK/releases)
e instale a SDK no serviço consumidor fixando a tag:

```bash
pip install git+https://github.com/prefeiturasp/SME-Sidecar-SDK.git@v1.0.0
```

## Variáveis obrigatórias por feature

Configure por variável de ambiente apenas os valores que dependem do ambiente,
infraestrutura ou segredo.

### Base

Obrigatória para identificar o ambiente nos logs e traces:

```bash
SME_ENVIRONMENT=local
```

### Tracing OpenTelemetry

Obrigatórias quando o envio de traces estiver habilitado:

```bash
SME_OTEL_ENABLED=true
SME_OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200
```

Obrigatória quando o endpoint OTLP exigir autenticação:

```bash
SME_OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer%20token
```

### Logs estruturados via RabbitMQ

Obrigatórias quando o envio de logs para fila estiver habilitado:

```bash
SME_BROKER_URL=amqp://usuario:senha@localhost:5672/%2F
SME_LOG_QUEUE=ms.pedagogico.logs
```

Configure a identidade do serviço no boot da aplicação. O nome lógico e a
versão pertencem ao artefato publicado, por isso podem ser informados pelo
código ao inicializar o runtime.

(integracao-django)=
## Integração com Django

### Inicializar o runtime

Inicialize a SDK uma vez no boot do processo Django, preferencialmente no
`AppConfig` do app `core`.

`apps/core/apps.py`:

```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configuração do app core."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self) -> None:
        """Inicializa os recursos compartilhados da SDK."""
        from sme_sidecar_sdk import runtime
        from sme_sidecar_sdk.config import Settings

        runtime.configure(
            Settings(
                service_name="pedagogico-ms",
                service_version="1.0.0",
            )
        )
```

O runtime combina os valores informados por código com as variáveis
`SME_*`, configura logging e inicializa tracing quando estiver habilitado. A
referência completa fica em {doc}`configuration`.

### Registrar o middleware

Adicione o middleware da SDK antes das camadas que emitem logs:

```python
MIDDLEWARE = [
    "sme_sidecar_sdk.integrations.django.ObservabilityMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]
```

O middleware reutiliza ou gera o `X-Request-ID`, devolve esse valor na
resposta e registra o log HTTP da requisição. Quando tracing está ativo,
a instrumentação oficial do OpenTelemetry para Django cria os spans HTTP.

## Como Utilizar Os Recursos

### Cliente HTTP compartilhado

Use o cliente HTTP da SDK para chamadas entre serviços. Ele já embute
timeout, retry, circuit breaker, logging, tracing e propagação de headers.

```python
from sme_sidecar_sdk import build_http_client

with build_http_client(
    "pedagogico-ms",
    base_url="https://pedagogico.exemplo.gov.br",
) as client:
    response = client.get("/api/v1/turmas")
    turmas = response.json()
```

O primeiro argumento (`"pedagogico-ms"`) identifica o upstream nos logs e
no circuit breaker.

Para código assíncrono, use o equivalente async:

```python
from sme_sidecar_sdk import build_async_http_client

async with build_async_http_client(
    "pedagogico-ms",
    base_url="https://pedagogico.exemplo.gov.br",
) as client:
    response = await client.get("/api/v1/turmas")
    turmas = response.json()
```

### Logs estruturados

Use `get_logger()` para emitir logs no padrão da SDK:

```python
from sme_sidecar_sdk import get_logger

log = get_logger(__name__)
log.info("turmas_consultadas", quantidade=12)
```

Os logs recebem automaticamente `service`, `environment`, `request_id` e,
quando houver span ativo, `trace_id` e `span_id`.

### Tracing OpenTelemetry

Depois do `runtime.configure()` e do `ObservabilityMiddleware`, o tracing não
exige chamadas manuais no código de negócio. A instrumentação cria spans para
as requisições Django e para as chamadas feitas com o cliente HTTP da SDK.

```python
from sme_sidecar_sdk import build_http_client


def listar_turmas() -> list[dict]:
    with build_http_client(
        "pedagogico-ms",
        base_url="https://pedagogico.exemplo.gov.br",
    ) as client:
        response = client.get("/api/v1/turmas")
        response.raise_for_status()
        return response.json()
```

Ao atender uma requisição Django, a chamada acima fica correlacionada ao trace
da requisição original. No APM, o endpoint Django aparece como transação e a
chamada para `pedagogico-ms` aparece como span HTTP externo.

### Contexto fora de uma requisição Django

Em workers, scripts ou integrações sem middleware HTTP, use
`request_context()` para criar ou reaproveitar o contexto de correlação:

```python
from sme_sidecar_sdk.observability import request_context

def processar(headers: dict[str, str]) -> None:
    with request_context(headers):
        ...
```

Dentro desse escopo, logs e chamadas feitas pelo cliente HTTP da SDK usam
o mesmo `X-Request-ID`.

### Primitivos de resiliência isolados

O uso recomendado para chamadas HTTP é o cliente compartilhado. Quando
precisar dos primitivos isolados, eles continuam disponíveis:

```python
from sme_sidecar_sdk.resilience.retry import retry_policy


@retry_policy(exceptions=(ConnectionError, TimeoutError))
def carregar_dados() -> None:
    ...
```

```python
from sme_sidecar_sdk.resilience.circuit_breaker import get_circuit_breaker

breaker = get_circuit_breaker("turmas-api")


@breaker
def chamar_turmas() -> None:
    ...
```
