# Guia de resiliência

Este guia descreve os três primitivos de resiliência fornecidos pela
SDK — **timeout**, **retry** e **circuit breaker** — explicando o
problema que cada um resolve, o mecanismo adotado e como utilizá-los em
serviços consumidores.

```{contents}
:local:
:depth: 2
```

## Conceitos

Em sistemas distribuídos, qualquer chamada de rede pode falhar. As
falhas variam de soluços de milissegundos a indisponibilidades de
minutos. Sem mecanismos explícitos de proteção, uma falha em um
componente upstream tende a se propagar para todos os consumidores que
dependem dele, gerando o efeito conhecido como **cascata de falhas**.

Os três primitivos a seguir atuam em camadas distintas dessa proteção e
são complementares: timeout protege uma chamada individual, retry
protege uma sequência de tentativas e circuit breaker protege o destino
ao longo do tempo.

---

## Cenário 1 — Timeout padronizado

### O problema

Toda chamada entre microsserviços precisa decidir quanto tempo o cliente
está disposto a esperar por uma resposta. Quando esse limite não é
explicitamente definido, a biblioteca HTTP utilizada (httpx, requests,
urllib) aplica seu próprio padrão — frequentemente **infinito** ou
ordem de minutos.

Sem timeout, na prática:

1. O upstream apresenta lentidão (deadlock de banco, pod travado,
   sobrecarga momentânea).
2. A thread responsável pela chamada fica bloqueada aguardando uma
   resposta que pode nunca chegar.
3. Novas requisições continuam chegando ao serviço consumidor, ocupando
   mais threads no mesmo estado.
4. O pool de threads se esgota e o serviço consumidor torna-se
   indisponível, mesmo sem apresentar qualquer falha intrínseca.

Esse é o gatilho clássico de cascata de falhas: o problema do upstream
se torna o problema do consumidor. Timeout é a primeira linha de defesa
contra esse efeito.

### Por que "padronizado"

A prática de definir o timeout caso a caso, distribuída pelo código,
tende a produzir inconsistências:

```python
requests.get(url, timeout=10)     # arquivo A
httpx.get(url, timeout=5)         # arquivo B
httpx.get(url)                    # arquivo C — timeout omitido
```

Três valores diferentes coexistem no mesmo serviço, sendo um deles
ausente. Em produção, isso dificulta a previsibilidade do comportamento
e a investigação de incidentes.

A SDK resolve essa inconsistência por **convenção do serviço**: toda chamada
HTTP criada via `build_sync_client()` ou `build_async_client()` herda o
timeout configurado, sem necessidade de repeti-lo a cada chamada. Consulte
{doc}`configuration` para opções e valores padrão.

### Uso

```python
from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.resilience.timeout import build_sync_client

settings = Settings(timeout_seconds=2.0)

with build_sync_client(settings) as client:
    response = client.get("http://upstream.local/recurso")
```

Quando o upstream demora mais do que o configurado, o cliente levanta
`httpx.ReadTimeout` (subclasse de `httpx.TimeoutException`) e libera a
thread imediatamente.

### Verificação

A medição da duração efetiva confirma o comportamento:

```python
import time
import httpx

start = time.perf_counter()
try:
    with build_sync_client(settings) as client:
        client.get("http://upstream.lento/")
except httpx.TimeoutException:
    elapsed = time.perf_counter() - start
    print(f"Timeout em {elapsed:.2f}s")
```

Configurando o timeout em 2 segundos contra um upstream que responderia
em 15 segundos, o valor de `elapsed` ficará próximo de 2 — evidência de
que o cliente interrompeu a chamada no limite definido.

---

## Cenário 2 — Retry para falhas temporárias

### O problema

Nem toda falha em sistemas distribuídos é definitiva. Uma fração
significativa dos erros é **transitória**, com duração de poucos
milissegundos a alguns segundos:

- Pico de tráfego no upstream resulta em um 503 momentâneo.
- Banco de dados realiza failover e fica indisponível por curto período.
- Soluços de rede (DNS, balanceador, reinício de pod).
- Locks no banco que se resolvem imediatamente após a primeira tentativa.

Propagar essas falhas diretamente ao cliente final transforma uma
indisponibilidade efêmera em erro visível, mesmo quando uma única nova
tentativa, segundos depois, teria recuperado a operação.

### Por que "com backoff exponencial"

Retry sem espaçamento gera o efeito **thundering herd**:

1. Um upstream sobrecarregado responde com 503.
2. Múltiplos clientes retentam imediatamente, na mesma janela.
3. O upstream recebe mais carga e a situação se agrava.
4. As falhas se sustentam ou pioram em vez de se resolverem.

Backoff exponencial introduz uma pausa crescente entre tentativas
(`0.5s`, `1s`, `2s`, `4s`, …), com efeitos benéficos:

- A primeira retry permanece rápida, suficiente para atravessar soluços
  curtos.
- As tentativas subsequentes se espalham no tempo, reduzindo a pressão
  sobre o upstream.
- Múltiplos clientes deixam de retentar em sincronia, evitando picos
  artificiais.

A SDK utiliza Tenacity como mecanismo subjacente. Como no timeout, a
configuração é definida por serviço, não por chamada. Consulte
{doc}`configuration` para opções e valores padrão.

### Uso

```python
from sme_sidecar_sdk import UpstreamHTTPError
from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.resilience.retry import retry_policy
from sme_sidecar_sdk.resilience.timeout import build_sync_client

settings = Settings(retry_attempts=3)


@retry_policy(settings=settings, exceptions=(UpstreamHTTPError,))
def consulta_turmas() -> dict:
    with build_sync_client(settings) as client:
        response = client.get("http://upstream.local/turmas")
        response.raise_for_status()  # 4xx/5xx vira UpstreamHTTPError
        return response.json()
```

Caso as primeiras tentativas levantem `UpstreamHTTPError`, novas
tentativas são realizadas após o backoff até atingir o limite
configurado. Quando o limite é atingido sem sucesso, a última exceção é
reerguida e cabe ao chamador tratá-la.

### Fronteira do mecanismo

É importante observar que o retry **deve falhar** quando o problema não
é transitório:

| Configuração | Cenário | Resultado |
|---|---|---|
| `attempts=3`, upstream falha 2x e recupera | falha transitória | sucesso na 3ª tentativa |
| `attempts=2`, upstream falha indefinidamente | falha persistente | erro propagado após a 2ª |

Esta fronteira é deliberada: retry não pode mascarar falhas eternas, sob
o risco de tornar o problema invisível à observabilidade e à
operação.

---

## Cenário 3 — Circuit breaker para evitar cascata de falhas

### O problema

Timeout e retry agem sobre chamadas individuais. Quando o upstream
permanece indisponível por períodos significativos — minutos ou mais —
esses mecanismos isolados tornam-se insuficientes.

Considere o cenário a seguir:

- O upstream está completamente indisponível por 5 minutos.
- O serviço consumidor continua recebendo 1000 requisições por minuto.
- Para cada requisição, uma chamada ao upstream é iniciada e aguarda o
  timeout de 10 segundos antes de desistir.

Resultado: cada uma das 1000 requisições mantém uma thread bloqueada por
10 segundos. Em pouco tempo o pool de threads se esgota, e o serviço
consumidor também se torna indisponível — inclusive em rotas que não
dependem do upstream caído. Ao final do incidente, quando o upstream
voltar, o consumidor irá despejar sobre ele toda a fila acumulada,
podendo provocar nova queda.

A solução requer um mecanismo com **memória**, capaz de identificar o
padrão de falhas e interromper temporariamente as chamadas ao destino
problemático.

### Mecanismo

O circuit breaker funciona como o disjuntor de um circuito elétrico.
Sob excesso de corrente — ou, no caso de software, sob excesso de
falhas consecutivas — ele **abre**, interrompendo a passagem.

São três estados:

- **Closed**: estado normal de operação. As chamadas passam pelo
  breaker e seguem para o upstream.
- **Open**: depois de atingido o limiar de falhas consecutivas, o
  breaker abre. As chamadas subsequentes são bloqueadas pelo próprio
  breaker, sem atingir a rede.
- **Half-open**: após o tempo de espera configurado, o breaker libera
  uma única chamada de teste. Se a chamada for bem-sucedida, o breaker
  retorna ao estado fechado; caso contrário, retorna ao estado aberto.

A SDK utiliza PyBreaker como mecanismo subjacente. O limiar de falhas e o
tempo de recuperação são definidos por serviço, conforme
{doc}`configuration`.

### Uso

```python
from sme_sidecar_sdk import CircuitOpenError, UpstreamHTTPError
from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.resilience.circuit_breaker import get_circuit_breaker
from sme_sidecar_sdk.resilience.timeout import build_sync_client

settings = Settings(circuit_breaker_fail_max=3)
breaker = get_circuit_breaker("turmas-upstream", settings)


def consulta_turmas() -> dict:
    with build_sync_client(settings) as client:
        response = client.get("http://upstream.local/turmas")
        response.raise_for_status()
        return response.json()


try:
    payload = breaker.call(consulta_turmas)
except CircuitOpenError:
    # Breaker aberto: a chamada foi bloqueada antes da rede.
    payload = {"fallback": True}
```

Duas exceções, com semânticas distintas:

- `UpstreamHTTPError`: a chamada alcançou o upstream e recebeu uma
  resposta de erro. Consumiu tempo e recursos de rede.
- `CircuitOpenError`: o breaker bloqueou a chamada antes da rede. O
  custo é da ordem de microsegundos.

### Impacto operacional

A diferença prática entre operar com e sem circuit breaker, em um
cenário de upstream indisponível por 5 minutos com 100 requisições no
consumidor, é resumida abaixo:

| Métrica | Sem breaker | Com breaker (`fail_max=3`) |
|---|---|---|
| Chamadas HTTP efetivamente feitas | 100 | 3 |
| Threads bloqueadas em timeout | até 100 × 10s | apenas 3 × 10s |
| Carga aplicada sobre upstream caído | máxima | mínima |
| Tempo de resposta após a 3ª falha | 10s por chamada | microsegundos |
| Recuperação do upstream | dificultada por carga residual | livre |

O circuit breaker é o único primitivo que atua sobre o padrão de falhas,
não sobre a chamada individual. Por essa razão, é considerado
obrigatório em arquiteturas de microsserviços de produção.

---

## Síntese

Os três primitivos atuam em camadas complementares de proteção:

| Primitivo | Pergunta que responde | Escala de proteção |
|---|---|---|
| **Timeout** | Quanto tempo aguardar uma resposta? | Uma chamada |
| **Retry** | Vale tentar de novo após uma falha? | Sequência de tentativas |
| **Circuit breaker** | Vale insistir quando tudo está falhando? | Destino, ao longo do tempo |

A ausência de qualquer uma delas compromete o conjunto:

- Timeout sem retry deixa o consumidor vulnerável a soluços
  transitórios.
- Retry sem circuit breaker amplifica cascatas de falhas em
  indisponibilidades prolongadas.
- Circuit breaker sem timeout falha em detectar travamentos sem retorno
  de erro explícito.

A SDK entrega os três primitivos configurados por convenção, garantindo
que cada serviço consumidor herde o comportamento resiliente sem
duplicação de código ou divergência entre implementações.
