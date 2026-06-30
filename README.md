# SME Sidecar SDK

> Runtime SDK **in-process** que entrega resiliência, logs estruturados
> e tracing distribuído sem sidecar container e sem hop de rede.

[![python](https://img.shields.io/badge/python-3.12-blue.svg)]()
[![license](https://img.shields.io/badge/license-AGPL--3.0-green.svg)]()

## Objetivo e escopo

A SME Sidecar SDK padroniza recursos transversais em aplicações Python,
com foco em serviços Django que realizam chamadas HTTP para outros
microsserviços. A SDK centraliza resiliência, correlação, logs
estruturados e tracing distribuído sem exigir um container sidecar.

Use a SDK para integrar aplicações aos padrões de observabilidade e
resiliência da SME. Regras de negócio, autenticação e contratos
específicos de cada serviço permanecem sob responsabilidade da
aplicação.

## Instalação

```bash
pip install git+https://github.com/prefeiturasp/SME-Sidecar-SDK.git
```

A aplicação consome a SDK assim:

```python
from sme_sidecar_sdk import runtime

runtime.configure()
```

## Features

- timeout padronizado em `httpx` (sync e async);
- retry com backoff exponencial via `tenacity`;
- circuit breaker via `pybreaker`;
- cliente HTTP compartilhado com timeout, retry, circuit breaker, logs,
  tracing e propagação de headers;
- logs JSON com serviço, ambiente, request ID, trace ID e span ID;
- propagação automática de `X-Request-ID` nos clientes HTTP do SDK;
- tracing OpenTelemetry com exportação OTLP para backend de observabilidade;
- provider assíncrono opcional de logs para fila.

> A explicação conceitual de cada primitivo, com exemplos executáveis e
> impacto operacional, está na documentação
> viva: `docs` (rodar `make livehtml` em `docs/` ou
> acessar a versão publicada).

## Integração com Django

> Consulte a documentação para integração correta.

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

Registre o middleware da SDK antes dos demais middlewares do projeto:

```python
MIDDLEWARE = [
    "sme_sidecar_sdk.integrations.django.ObservabilityMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]
```

## Desenvolvimento

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,docs]"
pre-commit install

pytest
pre-commit run --all-files
```

## Documentação viva (Sphinx)

A documentação completa — incluindo o **Guia de resiliência**, o
**Getting Started** e a referência da API — é gerada pelo Sphinx a
partir das docstrings do código e dos arquivos em `docs/`.

Documentação publicada:
[prefeiturasp.github.io/SME-Sidecar-SDK](https://prefeiturasp.github.io/SME-Sidecar-SDK/)

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
  tracing e backend de observabilidade.
- `configuration.md` — referência completa das variáveis de ambiente.
- `arquitetura.md` — princípio de empacotamento adotado
  (feature-based) e critérios para contribuições alinhadas.
- `api/` — referência automática da API a partir das docstrings.

## Licença

GNU Affero General Public License v3.0 (AGPL-3.0). Texto completo em
[`LICENSE`](LICENSE).
