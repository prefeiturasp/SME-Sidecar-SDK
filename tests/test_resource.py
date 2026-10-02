from __future__ import annotations

from pathlib import Path

import pytest

from sme_sidecar_sdk.config import Settings
from sme_sidecar_sdk.observability import resource


def test_detect_container_id_from_cgroup(tmp_path: Path) -> None:
    container_id = "a" * 64
    cgroup = tmp_path / "cgroup"
    cgroup.write_text(f"0::/docker/{container_id}\n", encoding="utf-8")

    assert resource.detect_container_id(cgroup, tmp_path / "hostname") == (
        container_id
    )


def test_detect_container_id_from_hostname(tmp_path: Path) -> None:
    hostname = tmp_path / "hostname"
    hostname.write_text("abcdef123456\n", encoding="utf-8")

    assert resource.detect_container_id(tmp_path / "cgroup", hostname) == (
        "abcdef123456"
    )


def test_build_resource_attributes_includes_ecs_service_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resource, "_get_hostname", lambda: "host-1")
    monkeypatch.setattr(resource, "detect_container_id", lambda: "abc123")

    attributes = resource.build_resource_attributes(
        Settings(
            SME_SERVICE_NAME="gateway-ms",
            SME_SERVICE_VERSION="1.0.0",
            SME_ENVIRONMENT="qa",
        )
    )

    assert attributes["service.name"] == "gateway-ms"
    assert attributes["service.version"] == "1.0.0"
    assert attributes["service.environment"] == "qa"
    assert attributes["deployment.environment"] == "qa"
    assert attributes["service.instance.id"] == "host-1"
    assert attributes["host.name"] == "host-1"
    assert attributes["container.id"] == "abc123"
