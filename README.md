# SME Sidecar SDK

> Runtime SDK **in-process** que entrega resiliência, logs estruturados
> e tracing distribuído sem sidecar container e sem hop de rede.

[![python](https://img.shields.io/badge/python-3.12-blue.svg)]()
[![license](https://img.shields.io/badge/license-AGPL--3.0-green.svg)]()

## Instalação

```bash
pip install git+https://github.com/prefeitura-sp/sme-sidecar-sdk.git
```

A aplicação consome a SDK assim:

```python
from sme_sidecar_sdk import runtime

runtime.configure()
```

A partir daí ficam ativos:

- timeout padronizado em `httpx` (sync e async);
- retry com backoff exponencial via `tenacity`;
- circuit breaker via `pybreaker`.
- logs JSON com serviço, ambiente, request ID, trace ID e span ID;
- propagação automática de `X-Request-ID` nos clientes HTTP do SDK;
- tracing OpenTelemetry com exportação OTLP para collector ou Elastic APM.
- provider assíncrono opcional de logs para RabbitMQ.

> A explicação conceitual de cada primitivo, com exemplos rodáveis e
> impacto operacional, está no **Guia de resiliência** da documentação
> viva: `docs/guia_resiliencia.md` (rodar `make livehtml` em `docs/` ou
> acessar a versão publicada).

## Estrutura

```
src/sme_sidecar_sdk/
  __init__.py
  runtime.py
  config.py
  observability/
    __init__.py
    context.py
    tracing.py
    logging/
      __init__.py
      configuration.py
      providers/
        base.py
        factory.py
        rabbitmq.py
  resilience/
    timeout.py
    retry.py
    circuit_breaker.py
```

## Integração com Django

Em projetos Django, o ponto correto para inicializar o runtime é o
método `ready()` do `AppConfig` de um dos apps carregados em
`INSTALLED_APPS` (convencionalmente o app `core` do projeto). Isso
garante que `runtime.configure()` execute **uma única vez** durante o
boot, antes da primeira requisição.

`apps/core/apps.py`:

```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configuração do app core."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self) -> None:
        """Inicializa o runtime do SME Sidecar SDK no boot do Django."""
        from sme_sidecar_sdk import runtime

        runtime.configure()
```

Pontos importantes:

- O import dentro de `ready()` (não no topo do módulo) evita problemas
  de inicialização circular e mantém o `apps.py` carregável mesmo em
  cenários onde a SDK ainda não esteja instalada.
- O método `ready()` é executado pelo Django uma vez por processo. Em
  servidores multi-worker (gunicorn, uvicorn), `configure()` será
  chamado em cada worker — comportamento esperado, dado que cada worker
  é um processo independente.
- O runtime configura logging e instrumenta chamadas `httpx` quando tracing
  está habilitado. O middleware da aplicação deve abrir o contexto da
  requisição recebida com `correlation_context()` e `use_trace_context()`.

Após a integração, as chamadas a serviços externos passam a usar os
primitivos da SDK em vez de instâncias cruas de `httpx`/`requests`. A
seção **Uso** de cada cenário no Guia de resiliência traz exemplos
prontos.

### Integração com outros frameworks

O padrão é equivalente em outros frameworks: chame `runtime.configure()`
**uma única vez** no boot da aplicação.

- **FastAPI / Starlette**: dentro do `lifespan` ou em um evento de
  `startup`.
- **Flask**: no factory da aplicação, após a criação da instância `Flask`.
- **Scripts e workers**: no início da função principal, antes de qualquer
  chamada de rede.

## Variáveis de ambiente

A descrição detalhada de cada variável está em
`docs/configuration.md` (acessível no Sphinx).

## Desenvolvimento

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,docs]"
pre-commit install

pytest
ruff check src tests
mypy src
```

## Documentação viva (Sphinx)

A documentação completa — incluindo o **Guia de resiliência**, o
**Getting Started** e a referência da API — é gerada pelo Sphinx a
partir das docstrings do código e dos arquivos em `docs/`.

```bash
cd docs
make livehtml   # abre em http://127.0.0.1:8000 com hot-reload
```

Build estático:

```bash
cd docs
make html       # gera HTML em docs/_build/html
```

Páginas principais:

- `index.rst` — visão geral.
- `getting_started.md` — instalação e uso básico.
- `guia_resiliencia.md` — explicação dos três primitivos (problema,
  mecanismo, uso, impacto).
- `guia_observabilidade.md` — integração completa de logs, correlação,
  tracing e Elastic APM.
- `configuration.md` — referência completa das variáveis de ambiente.
- `arquitetura.md` — princípio de empacotamento adotado
  (feature-based) e critérios para contribuições alinhadas.
- `api/` — referência automática da API a partir das docstrings.

## Licença

GNU Affero General Public License v3.0 (AGPL-3.0). Texto completo em
[`LICENSE`](LICENSE).
