# Getting Started

## Instalação

```bash
pip install sme-sidecar-sdk
```

## Configuração mínima

```python
from sme_sidecar_sdk import runtime

state = runtime.configure()
print(state.settings.service_name)
```

O `configure()` lê variáveis `SME_*` do ambiente (ou de um `.env`) e
deixa o `state` disponível para inspeção.

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
