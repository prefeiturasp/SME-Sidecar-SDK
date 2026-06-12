# Getting Started

## Instalação

```bash
pip install git+https://github.com/prefeiturasp/SME-Sidecar-SDK.git
```

## Configuração mínima

```python
from sme_sidecar_sdk import runtime

state = runtime.configure()
print(state.settings.service_name)
```

O `configure()` lê a configuração do ambiente, configura os logs e,
quando habilitado, inicializa o tracing. Consulte {doc}`configuration`
para opções e valores padrão.

(integracao-django)=
## Integração com Django

Inicialize a SDK uma vez no boot de cada processo por meio do `ready()` do
`AppConfig`, preferencialmente no app `core`:

```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configuração do app core."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self) -> None:
        """Inicializa os recursos compartilhados da SDK."""
        from sme_sidecar_sdk import runtime

        runtime.configure()
```

O import dentro de `ready()` evita problemas de inicialização circular. Em
servidores com múltiplos workers, o Django executa o método uma vez em cada
processo, que é o comportamento esperado para logging e tracing.

Confirme que o app está registrado em `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    "apps.core.apps.CoreConfig",
]
```

Registre o middleware fornecido pela SDK antes das camadas que emitem
logs:

```python
MIDDLEWARE = [
    "sme_sidecar_sdk.integrations.django.ObservabilityMiddleware",
    "django.middleware.security.SecurityMiddleware",
]
```

O middleware reutiliza ou gera o `X-Request-ID`, devolve o identificador
na resposta, registra método, path, status e duração e cria o span
`django.request` quando o tracing está habilitado.

O tracing é opt-in. Quando desabilitado, os logs e a correlação continuam
funcionando, mas nenhum span é exportado. Consulte {doc}`configuration`
para conhecer as opções disponíveis.

## Logs estruturados

```python
from sme_sidecar_sdk import get_logger

log = get_logger(__name__)
log.info("turmas_consultadas", quantidade=12)
```

Logs emitidos pelo `logging` padrão também usam o mesmo formato.

## Envio opcional de logs ao RabbitMQ

Com a URL do broker injetada pela infraestrutura, cada aplicação precisa
informar somente sua fila:

```bash
SME_LOG_RABBITMQ_QUEUE=ms.pedagogico.logs
```

O runtime detecta a fila, conecta o provider automaticamente e publica os
logs estruturados em background. Nenhuma configuração de logging Django é
necessária.

## Contexto de uma requisição recebida

```python
from sme_sidecar_sdk.observability import get_tracer, request_context

def processar(headers):
    with request_context(headers):
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("processar_requisicao"):
            ...
```

O contexto deve ser aberto pelo middleware HTTP da aplicação. Se o header
`X-Request-ID` não existir, o SDK gera um UUID. Os clientes construídos pelo
SDK propagam esse identificador e, com tracing habilitado, o contexto W3C.

## Usando os clientes HTTP com timeout padronizado

```python
from sme_sidecar_sdk.resilience.timeout import build_sync_client

with build_sync_client() as client:
    response = client.get("https://api.exemplo.gov.br/v1/turmas")
```

## Retry com backoff exponencial

```python
from sme_sidecar_sdk.resilience.retry import retry_policy

@retry_policy(exceptions=(ConnectionError, TimeoutError))
def carrega_turmas():
    ...
```

## Circuit breaker

```python
from sme_sidecar_sdk.resilience.circuit_breaker import get_circuit_breaker

breaker = get_circuit_breaker("turmas-api")

@breaker
def chama_turmas():
    ...
```
