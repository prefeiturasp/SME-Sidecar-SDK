# Configuração via variáveis de ambiente

Todas as variáveis da SDK usam o prefixo `SME_`. A tabela de cada grupo
apresenta o valor padrão aplicado quando a variável não é informada.

## Master switch e identidade

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `SME_SDK_ENABLED` | `true` | Liga ou desliga todos os recursos inicializados pelo runtime. |
| `SME_SERVICE_NAME` | `unnamed-service` | Nome lógico usado para identificar o serviço em logs e traces. |
| `SME_SERVICE_VERSION` | `unknown` | Versão publicada do serviço enviada como atributo dos traces. |
| `SME_ENVIRONMENT` | `dev` | Ambiente exibido em logs e traces, como `dev`, `qa` ou `production`. |

## Resiliência

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `SME_TIMEOUT_ENABLED` | `true` | Habilita o timeout padronizado nos clientes HTTP da SDK. |
| `SME_TIMEOUT_SECONDS` | `10` | Tempo máximo, em segundos, aguardado por uma chamada HTTP. |
| `SME_RETRY_ENABLED` | `true` | Habilita novas tentativas para as exceções definidas pelo consumidor. |
| `SME_RETRY_ATTEMPTS` | `3` | Total máximo de tentativas, incluindo a chamada inicial. |
| `SME_RETRY_BACKOFF_MIN` | `0.5` | Intervalo mínimo, em segundos, do backoff exponencial. |
| `SME_RETRY_BACKOFF_MAX` | `5` | Intervalo máximo, em segundos, do backoff exponencial. |
| `SME_CIRCUIT_BREAKER_ENABLED` | `true` | Habilita a proteção por circuit breaker. |
| `SME_CIRCUIT_BREAKER_FAIL_MAX` | `5` | Falhas consecutivas necessárias para abrir o circuito. |
| `SME_CIRCUIT_BREAKER_RESET_TIMEOUT` | `30` | Tempo, em segundos, antes de testar a recuperação do destino. |

## Logs e correlação

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `SME_LOGGING_ENABLED` | `true` | Habilita a configuração centralizada de `structlog` e `logging`. |
| `SME_LOG_LEVEL` | `ERROR` | Nível mínimo emitido: `DEBUG`, `INFO`, `WARNING`, `ERROR` ou `CRITICAL`. |
| `SME_LOG_FORMAT` | `json` | Formato de saída: `json` para ambientes integrados ou `console` para desenvolvimento. |
| `SME_CORRELATION_ID_HEADER` | `X-Request-ID` | Nome do header recebido, gerado e propagado entre serviços. |

## Provider de fila para logs

O provider é ativado quando `SME_LOG_QUEUE` possui um valor. A aplicação
não configura handlers nem importa dependências do broker: o runtime adiciona
o provider automaticamente ao logging estruturado.

Atualmente, `rabbitmq` é a única implementação disponível de broker e usa
`pika` internamente. A integração com Redis, Kafka, SQS ou outros brokers
exige a criação de uma nova implementação de provider.

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `SME_BROKER` | `rabbitmq` | Broker usado pelo provider de fila de logs. Atualmente, apenas `rabbitmq` é suportado. |
| `SME_BROKER_URL` | `amqp://guest:guest@localhost:5672/%2F` | Conexão compartilhada, preferencialmente injetada pela infraestrutura em todos os serviços. |
| `SME_LOG_QUEUE` | vazio | Fila específica do microsserviço. Quando vazia, o provider permanece desabilitado. |
| `SME_LOG_QUEUE_BUFFER_SIZE` | `10000` | Máximo de mensagens aguardando publicação no buffer local. |
| `SME_LOG_QUEUE_SOCKET_TIMEOUT` | `2` | Timeout de conexão em segundos, executado fora da thread da requisição. |
| `SME_LOG_QUEUE_POLL_INTERVAL` | `0.25` | Intervalo de leitura do buffer pelo worker. |
| `SME_LOG_QUEUE_SHUTDOWN_TIMEOUT` | `2` | Tempo máximo de espera pelo worker durante o encerramento. |

Configuração comum da infraestrutura:

```bash
SME_BROKER_URL=amqp://usuario:senha@rabbitmq:5672/vhost
```

Configuração que varia em cada microsserviço:

```bash
SME_LOG_QUEUE=ms.pedagogico.logs
```

O `emit()` não executa I/O de rede. Ele adiciona o JSON estruturado a um
buffer limitado e retorna imediatamente. A publicação ocorre em uma thread
daemon. Se o buffer estiver cheio ou o broker indisponível, a API continua
respondendo e o `stdout` permanece como fallback.

## OpenTelemetry e backend de observabilidade

A SDK exporta traces usando OpenTelemetry e OTLP. Atualmente, `elastic` é
o único backend de observabilidade homologado. Backends como Jaeger,
Grafana Tempo, Datadog, New Relic ou outros destinos compatíveis com OTLP
exigem validação de configuração, documentação própria e, se necessário,
ajustes de implementação.

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `SME_OBSERVABILITY_BACKEND` | `elastic` | Backend de observabilidade suportado pela configuração documentada. Atualmente, apenas `elastic` é aceito. |
| `SME_OTEL_ENABLED` | `false` | Habilita provider, exporter e instrumentações HTTPX/Django. |
| `SME_OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | Endpoint OTLP gRPC do OpenTelemetry Collector ou backend compatível. |
| `SME_OTEL_EXPORTER_OTLP_HEADERS` | vazio | Headers de autenticação no formato `chave=valor`, separados por vírgula. Valores percent-encoded são decodificados pela SDK. |
| `SME_OTEL_EXPORTER_OTLP_INSECURE` | `true` | Quando `true`, usa transporte sem TLS; defina `false` para endpoints HTTPS. |

### Envio direto via OpenTelemetry

O envio direto utiliza OpenTelemetry e OTLP; ele apenas dispensa um Collector
intermediário. As variáveis de identidade do serviço, como
`SME_SERVICE_NAME`, `SME_SERVICE_VERSION` e `SME_ENVIRONMENT`, são globais
da SDK e ficam descritas em
<a href="#master-switch-e-identidade">Master switch e identidade</a>.
Para este cenário, configure somente o backend homologado e o exporter OTLP:

```bash
SME_OTEL_ENABLED=true
SME_OTEL_EXPORTER_OTLP_ENDPOINT=https://apm.exemplo:8200
SME_OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer%20seu-token
SME_OTEL_EXPORTER_OTLP_INSECURE=false
```

### Via OpenTelemetry Collector

Use um Collector quando a infraestrutura precisar centralizar autenticação,
amostragem, processamento ou roteamento. O backend continua sendo `elastic`
quando o Collector encaminha os dados para o Elastic APM:

```bash
SME_OTEL_ENABLED=true
SME_OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```
