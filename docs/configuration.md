# Configuração via variáveis de ambiente

Todas as variáveis usam o prefixo `SME_`. Valores padrão entre parênteses.

## Master switch e identidade

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `SME_SDK_ENABLED` | `true` | Liga/desliga o runtime inteiro. |
| `SME_SERVICE_NAME` | `unnamed-service` | Nome lógico do serviço. |
| `SME_ENVIRONMENT` | `dev` | Ambiente (`dev`, `qa`, `prod`). |

## Resiliência

| Variável | Padrão |
| --- | --- |
| `SME_TIMEOUT_ENABLED` | `true` |
| `SME_TIMEOUT_SECONDS` | `10` |
| `SME_RETRY_ENABLED` | `true` |
| `SME_RETRY_ATTEMPTS` | `3` |
| `SME_RETRY_BACKOFF_MIN` | `0.5` |
| `SME_RETRY_BACKOFF_MAX` | `5` |
| `SME_CIRCUIT_BREAKER_ENABLED` | `true` |
| `SME_CIRCUIT_BREAKER_FAIL_MAX` | `5` |
| `SME_CIRCUIT_BREAKER_RESET_TIMEOUT` | `30` |
