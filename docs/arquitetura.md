# Arquitetura

Este documento descreve a organização interna do código da SDK e o
princípio de empacotamento adotado. Destina-se a contribuidores e
revisores que precisam alterar ou estender o projeto.

```{contents}
:local:
:depth: 2
```

## Princípio: feature-based packaging

O código da SDK é organizado por **capacidade** (resiliência), e não
por camada técnica (controllers, services, repositories). Cada
primitivo de resiliência mora em um único módulo que contém tudo o que
o define: configuração lida, algoritmo, fábricas e exposição pública.

```
src/sme_sidecar_sdk/
├── __init__.py
├── runtime.py            # fachada pública
├── config.py             # configuração base
└── resilience/           # capacidade
    ├── __init__.py
    ├── timeout.py        # tudo sobre timeout
    ├── retry.py          # tudo sobre retry
    └── circuit_breaker.py# tudo sobre circuit breaker
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
fluírem em **uma direção**, dos blocos de infraestrutura para os
primitivos, e dos primitivos para a fachada — nunca lateralmente entre
primitivos.

```
config.py                ← infraestrutura (lida por todos)
   │
   ├── resilience/       ← capacidade (não enxerga outros pares)
   │
   └── runtime.py        ← fachada (orquestra)
```

Regras concretas verificáveis em revisão de código:

- Nada em `config.py` importa de subpacotes.
- Nenhum módulo dentro de `resilience/` importa outro irmão direto.
- Apenas `runtime.py` (ou o `__init__.py` da SDK) pode amarrar a
  exposição pública de múltiplos primitivos.

Quando uma nova capacidade for adicionada, ela deve viver em seu
próprio subpacote irmão de `resilience/`, sem acoplamento horizontal
entre eles.

## Como contribuir alinhado à arquitetura

Ao adicionar funcionalidade, alguns critérios mantêm a coerência:

1. **Crie um arquivo novo para uma capacidade nova.** Se a
   funcionalidade pertencer a uma nova categoria (ex: cache,
   serialização, autenticação), considere criar um subpacote irmão.
2. **Não importe entre primitivos irmãos.** Se dois módulos precisarem
   compartilhar algo, esse algo pertence a `config.py` ou a uma
   utilidade compartilhada explícita.
3. **Adicione testes espelhando a estrutura.** Cada
   `src/sme_sidecar_sdk/resilience/<x>.py` tem um par direto
   `tests/test_<x>.py`. Gaps de cobertura ficam evidentes nesse
   formato.
