SME Sidecar SDK
===============

Runtime SDK in-process que entrega resiliência, logs estruturados e tracing
distribuído sem sidecar container e sem hop de rede.

.. toctree::
   :maxdepth: 2
   :caption: Conteúdo

   getting_started
   guia_resiliencia
   guia_observabilidade
   configuration
   arquitetura
   api/index

Visão geral
-----------

Uma aplicação consumidora habilita o runtime com uma única chamada::

   from sme_sidecar_sdk import runtime

   runtime.configure()

Os pilares de resiliência (timeout, retry e circuit breaker) ficam
expostos via os módulos em :mod:`sme_sidecar_sdk.resilience` e reunidos
no cliente HTTP compartilhado em :mod:`sme_sidecar_sdk.http`.

Índices e tabelas
-----------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
