"""Atributos de recurso compartilhados por logs e tracing."""

from __future__ import annotations

import re
import socket
from pathlib import Path

from ..config import Settings

_CONTAINER_ID_RE = re.compile(r"(?P<id>[0-9a-f]{64})(?:\.scope)?")
_HOSTNAME_CONTAINER_RE = re.compile(r"[0-9a-f]{12,64}")


def _get_hostname() -> str:
    """Retorna o hostname do processo atual."""
    return socket.gethostname()


def detect_container_id(
    cgroup_path: Path = Path("/proc/self/cgroup"),
    hostname_path: Path = Path("/etc/hostname"),
) -> str | None:
    """Detecta o ID do container quando exposto pelo runtime.

    Args:
        cgroup_path: Caminho do arquivo de cgroup do processo.
        hostname_path: Caminho do hostname interno do container.

    Returns:
        ID do container quando detectado; caso contrário, ``None``.
    """
    try:
        content = cgroup_path.read_text(encoding="utf-8")
    except OSError:
        content = ""

    for match in _CONTAINER_ID_RE.finditer(content):
        return match.group("id")

    try:
        hostname = hostname_path.read_text(encoding="utf-8").strip()
    except OSError:
        hostname = ""
    if _HOSTNAME_CONTAINER_RE.fullmatch(hostname):
        return hostname
    return None


def build_resource_attributes(settings: Settings) -> dict[str, str]:
    """Monta atributos ECS/OpenTelemetry do processo atual.

    Args:
        settings: Configuração efetiva da SDK.

    Returns:
        Atributos usados em spans e logs estruturados.
    """
    hostname = _get_hostname()
    attributes = {
        "service.name": settings.service_name,
        "service.version": settings.service_version,
        "service.environment": settings.environment,
        "deployment.environment": settings.environment,
        "deployment.environment.name": settings.environment,
        "service.instance.id": hostname,
        "host.name": hostname,
    }
    container_id = detect_container_id()
    if container_id:
        attributes["container.id"] = container_id
    return attributes
