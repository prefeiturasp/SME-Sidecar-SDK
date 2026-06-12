# Guia de observabilidade

Este guia descreve os três recursos de observabilidade fornecidos pela
SDK — **logs estruturados**, **correlação de requisições** e **tracing
distribuído** — explicando o problema que cada um resolve, o mecanismo
adotado e como utilizá-los em serviços consumidores.

```{contents}
:local:
:depth: 2
```

## Conceitos

Em uma arquitetura distribuída, uma única operação pode atravessar
gateway, microsserviços e integrações externas. Sem um contexto comum,
cada serviço produz registros isolados e a investigação de falhas
depende da comparação manual de horários e mensagens.

Os três recursos atuam de forma complementar:

- logs estruturados registram os eventos de cada serviço;
- o request ID permite localizar eventos da mesma requisição;
- o trace distribuído representa o caminho completo entre os serviços.

O fluxo resultante é:

```text
Cliente
  -> serviço A recebe X-Request-ID e traceparent
  -> logs recebem request_id, trace_id e span_id
  -> cliente HTTPX propaga os identificadores
  -> serviço B continua a correlação e o trace
  -> spans são exportados via OTLP
  -> Elastic APM apresenta a cadeia completa
```

Antes de utilizar os exemplos, conclua a inicialização descrita em
{ref}`integracao-django`. Todas as opções e valores padrão estão em
{doc}`configuration`.

---

## Cenário 1 — Logs estruturados

### O problema

Logs em texto livre variam entre módulos e serviços. Campos importantes
podem aparecer com nomes diferentes ou misturados na mensagem, tornando
consultas, alertas e painéis pouco confiáveis.

Também é comum uma aplicação utilizar ao mesmo tempo o `logging` padrão
do Python e uma biblioteca de logs estruturados. Sem uma configuração
única, cada origem produz um formato diferente.

### Por que "padronizados"

`runtime.configure()` configura `structlog` e o `logging` padrão com o
mesmo pipeline. Cada evento JSON inclui:

- data e hora;
- nível e nome do logger;
- serviço e ambiente;
- nome do evento e seus campos de negócio;
- `request_id`, `trace_id` e `span_id`, quando disponíveis.

Essa estrutura permite consultar campos diretamente no mecanismo de
busca, sem interpretar o conteúdo textual de cada mensagem.

### Uso

```python
from sme_sidecar_sdk import get_logger

log = get_logger(__name__)
log.info(
    "turmas_consultadas",
    quantidade=12,
    ano_letivo=2026,
)
```

O `logging` padrão também é processado:

```python
import logging

log = logging.getLogger(__name__)
log.warning("upstream_temporariamente_indisponivel")
```

Exemplo de saída:

```json
{
  "timestamp": "2026-06-11T14:30:00Z",
  "level": "info",
  "logger": "apps.turmas.services",
  "event": "turmas_consultadas",
  "service": "pedagogico-ms",
  "environment": "production",
  "request_id": "8d624936-4ab1-4a89-9f0b-6632b91e13ef",
  "trace_id": "4fd0bca66d5c02185d06ad77b6dfed46",
  "span_id": "62e72c734d66304d",
  "quantidade": 12
}
```

Não registre senhas, tokens, documentos pessoais ou payloads completos
com informações sensíveis.

### Verificação

Emita um evento com o logger da SDK e outro com `logging.getLogger()`.
Ambos devem apresentar o mesmo formato e os campos de identidade do
serviço.

---

## Cenário 2 — Correlação e propagação de requisições

### O problema

Uma falha observada pelo cliente pode gerar dezenas de logs em serviços
diferentes. Sem um identificador propagado, não existe uma forma
determinística de separar os eventos daquela requisição dos demais
eventos ocorridos no mesmo período.

### Mecanismo

`request_context()` reutiliza o `X-Request-ID` recebido ou cria um UUID.
O identificador fica armazenado em `ContextVar`, permanecendo isolado
entre requisições síncronas e assíncronas.

O mesmo contexto extrai o header W3C `traceparent`. Dessa forma, a
correlação dos logs e a continuidade do trace são ativadas juntas.

### Uso em Django

```python
MIDDLEWARE = [
    "sme_sidecar_sdk.integrations.django.ObservabilityMiddleware",
    "django.middleware.security.SecurityMiddleware",
]
```

Registre o middleware antes das camadas que emitem logs.

### Propagação nas chamadas HTTP

Os clientes da SDK propagam automaticamente o `X-Request-ID`. Quando o
tracing está ativo, a instrumentação HTTPX também injeta `traceparent`.

```python
from sme_sidecar_sdk.resilience.timeout import build_sync_client

with build_sync_client() as client:
    response = client.get("https://servico-interno/api/v1/turmas")
```

Headers informados explicitamente e hooks definidos pela aplicação são
preservados.

Para transportes não baseados em HTTPX, utilize
`inject_trace_context()` na origem e `use_trace_context()` no destino.

### Verificação

Envie uma requisição com um `X-Request-ID` conhecido e faça uma chamada
para outro serviço usando o cliente da SDK. O mesmo valor deve aparecer:

1. na resposta do primeiro serviço;
2. nos logs dos dois serviços;
3. no header recebido pelo serviço de destino.

---

## Cenário 3 — Tracing distribuído com OpenTelemetry

### O problema

O request ID informa quais eventos pertencem à mesma requisição, mas não
representa duração, hierarquia ou dependência entre operações. Ele não
mostra, por exemplo, qual chamada consumiu mais tempo ou em qual serviço
um erro começou.

### Mecanismo

Quando habilitado, o runtime:

1. cria um `TracerProvider` com a identidade do serviço;
2. configura o exporter OTLP gRPC;
3. instrumenta automaticamente os clientes `httpx`;
4. adiciona `trace_id` e `span_id` aos logs durante spans ativos.

O protocolo OTLP permite enviar os spans a um OpenTelemetry Collector ou
diretamente a uma plataforma compatível, como o Elastic APM. Nos dois
casos, a instrumentação continua sendo exclusivamente OpenTelemetry.

O Collector é recomendado quando a infraestrutura precisa centralizar
autenticação, amostragem, processamento ou roteamento da telemetria.

### Spans manuais

Chamadas HTTP recebem spans automáticos. Operações de negócio relevantes
podem receber spans próprios:

```python
from sme_sidecar_sdk.observability import get_tracer

tracer = get_tracer(__name__)

with tracer.start_as_current_span("calcular_grade_curricular") as span:
    span.set_attribute("ano_letivo", 2026)
    resultado = calcular_grade()
    span.set_attribute("quantidade_componentes", len(resultado))
```

Evite atributos com alta cardinalidade ou informações sensíveis.
Prefira códigos, tipos, contagens e estados operacionais.

### Visualização no Elastic APM

No Elastic Observability:

1. localize o serviço pelo nome configurado;
2. filtre pelo ambiente;
3. abra uma transação para visualizar a cadeia de spans;
4. use `trace_id` para correlacionar traces e logs;
5. use `request_id` para incluir serviços ainda sem tracing.

### Verificação

Execute uma requisição que atravesse pelo menos dois serviços. O Elastic
deve apresentar um único trace com spans dos dois serviços e as chamadas
HTTP entre eles.

---

## Síntese

Os três recursos respondem a perguntas diferentes:

| Recurso | Pergunta que responde |
|---|---|
| **Logs estruturados** | O que aconteceu dentro de cada serviço? |
| **Request ID** | Quais eventos pertencem à mesma requisição? |
| **Tracing distribuído** | Qual foi o caminho, a duração e a dependência entre operações? |

O conjunto permite iniciar uma investigação por um erro de negócio,
localizar todos os logs relacionados e chegar ao trace completo da
operação no Elastic APM.

## Estratégia de testes

O comportamento pertencente à SDK deve ser garantido por testes unitários.
Responsabilidades da aplicação consumidora e da infraestrutura exigem testes
de integração ou validações operacionais.

### Garantias da SDK

| Comportamento | Verificação automatizada |
|---|---|
| Criação, reutilização e restauração do request ID | Testes unitários de `correlation_context()` e `request_context()` |
| Isolamento do contexto de execução | Testes unitários com `ContextVar` |
| Inclusão de contexto nos logs estruturados | Testes unitários de `structlog` e `logging` padrão |
| Propagação de `X-Request-ID` em HTTPX síncrono e assíncrono | Testes unitários com `MockTransport` |
| Preservação de headers e hooks definidos pelo consumidor | Testes unitários dos clientes HTTP |
| Injeção e extração de `traceparent` | Testes unitários de propagação OpenTelemetry |
| Configuração do exporter OTLP e instrumentação HTTPX | Testes unitários com exporter e instrumentador simulados |
| Valores padrão e leitura da configuração | Testes unitários de `Settings` |

Esses testes fazem parte da suíte da SDK e devem ser executados no CI antes da
publicação de uma nova versão.

### Responsabilidades do serviço consumidor

Cada aplicação deve possuir testes de integração que confirmem:

- inicialização da SDK no boot do processo;
- registro e posição correta do middleware;
- devolução de `X-Request-ID` na resposta HTTP;
- uso dos clientes HTTP fornecidos pela SDK;
- continuidade do request ID e do trace entre endpoints reais.

### Validações operacionais

Os itens abaixo dependem do ambiente e não podem ser garantidos por testes
unitários da SDK:

- conectividade e autenticação com o Collector ou Elastic APM;
- preservação de headers por gateways, proxies e balanceadores;
- indexação e correlação entre logs e traces no Elastic;
- ausência de informações sensíveis nos campos enviados pela aplicação;
- funcionamento de alertas, painéis e políticas de retenção.

Essas verificações devem compor testes de smoke, homologação e monitoramento
contínuo do ambiente.

## Referências

- [OpenTelemetry com Elastic APM](https://www.elastic.co/docs/solutions/observability/apm/opentelemetry)
- [Propagação OpenTelemetry](https://opentelemetry.io/docs/languages/python/propagation/)
- [Instrumentação HTTPX](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/httpx/httpx.html)
- [Exporter OTLP para Python](https://opentelemetry-python.readthedocs.io/en/latest/exporter/otlp/otlp.html)
