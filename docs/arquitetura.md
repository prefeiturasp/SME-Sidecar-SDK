# Arquitetura

Este documento descreve a organização interna do código da SDK e o
princípio de empacotamento adotado. Destina-se a contribuidores e
revisores que precisam alterar ou estender o projeto.

```{contents}
:local:
:depth: 2
```

## Princípio: feature-based packaging

O código da SDK é organizado por **capacidade**, e não por camada
técnica (controllers, services, repositories). Cada feature mantém
próximos seus contratos, implementações, fábricas e exposição pública.

```
src/sme_sidecar_sdk/
├── __init__.py
├── runtime.py            # fachada pública
├── config.py             # configuração base
├── resilience/           # capacidade
│   ├── __init__.py
│   ├── timeout.py        # tudo sobre timeout
│   ├── retry.py          # tudo sobre retry
│   └── circuit_breaker.py# tudo sobre circuit breaker
├── observability/        # domínio de observabilidade
│   ├── __init__.py       # fachada do domínio
│   ├── context.py        # correlação e contexto de requisição
│   ├── tracing.py        # tracing distribuído
│   └── logging/          # feature de logs estruturados
│       ├── __init__.py
│       ├── configuration.py
│       └── providers/
│           ├── base.py
│           ├── factory.py
│           └── rabbitmq.py
└── integrations/         # adaptadores de frameworks
    └── django.py
```

### Comparação com layer-based packaging

Em uma organização por camada técnica, o mesmo código ficaria
distribuído entre múltiplos arquivos especializados por tipo:

```
sme_sidecar_sdk/
├── factories/
│   ├── retry_factory.py
│   ├── breaker_factory.py
│   └── client_factory.py
├── configs/
│   ├── retry_config.py
│   ├── breaker_config.py
│   └── timeout_config.py
├── registries/
│   └── breaker_registry.py
└── decorators/
    └── retry_decorator.py
```

A diferença prática é resumida abaixo:

| Aspecto | Feature-based (adotado) | Layer-based |
|---|---|---|
| Compreender um primitivo | Abrir **um** arquivo | Abrir 3 a 4 arquivos espalhados |
| Remover uma capacidade | Apagar 1 módulo + 1 teste + 1 linha no `__init__` | Tocar múltiplas pastas |
| Localidade de mudança | Alterações ficam em arquivos próximos | Alterações se espalham por toda a árvore |
| Risco em refactor | Baixo | Alto |
| Adequação | Bibliotecas com capacidades autocontidas | Aplicações com lógica de negócio compartilhada |

### Regras de dependência

A organização por capacidade só permanece limpa se as dependências
fluírem em **uma direção**, da infraestrutura compartilhada para as
features e das features para as fachadas e integrações. Dependências
entre features devem representar composição explícita, não apenas
reutilização conveniente.

```
config.py                 ← infraestrutura compartilhada
   │
   ├── resilience/        ← capacidades de resiliência
   ├── observability/     ← contexto, tracing e logging
   ├── integrations/      ← adaptadores que compõem features
   └── runtime.py         ← fachada que orquestra o boot
```

Regras concretas verificáveis em revisão de código:

- Nada em `config.py` importa de subpacotes.
- Nenhum módulo dentro de `resilience/` importa outro irmão direto.
- Implementações específicas pertencem à feature que as utiliza. Por
  exemplo, providers RabbitMQ vivem em
  `observability/logging/providers/`, não em um pacote técnico na raiz.
- Correlação pertence ao contexto de observabilidade; logging e tracing
  consomem esse contexto para enriquecer e propagar telemetria.
- `runtime.py`, `integrations/` e os `__init__.py` públicos podem
  compor múltiplas features porque exercem papel de orquestração.
- Dependências compartilhadas de contexto podem ser usadas pelas
  features que enriquecem ou propagam esse contexto.

Quando uma nova capacidade for adicionada, ela deve viver em seu
próprio subpacote irmão de `resilience/`. Caso dependa de outra feature,
essa composição deve ser pequena, explícita e orientada ao fluxo da
aplicação.

## Como contribuir alinhado à arquitetura

Ao adicionar funcionalidade, alguns critérios mantêm a coerência:

1. **Crie um pacote para uma capacidade coesa.** Se a funcionalidade
   pertencer a uma nova categoria (ex: cache, serialização,
   autenticação), considere criar um subpacote irmão.
2. **Evite dependências acidentais entre features.** Se dois módulos
   precisarem compartilhar uma abstração neutra, ela pertence à
   infraestrutura compartilhada. Composições próprias do fluxo, como
   logging enriquecido por correlação, podem permanecer explícitas.
3. **Adicione testes espelhando as capacidades.** Os nomes dos testes
   devem deixar evidente qual feature e implementação estão sendo
   verificadas.
