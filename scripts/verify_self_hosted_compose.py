#!/usr/bin/env python3
"""Verify the production Compose privilege and exposure contract."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
APP_SERVICES = ("migrate", "api", "worker", "worker-video", "worker-ops", "scheduler")


def main() -> int:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.count("@sha256:") == 2
    assert "requirements.lock.txt" in dockerfile
    assert "pip install -r requirements.lock.txt" in dockerfile
    lock_lines = [
        line for line in (ROOT / "requirements.lock.txt").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    assert lock_lines and all("==" in line for line in lock_lines)
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    env = (ROOT / "compose.env.example").read_text(encoding="utf-8")
    services = compose["services"]

    for fragment in (
        "groupadd --gid 10001 miemie",
        "useradd --uid 10001 --gid 10001",
        "USER 10001:10001",
        'HOME="/tmp"',
    ):
        assert fragment in dockerfile, fragment

    for name in APP_SERVICES:
        service = services[name]
        assert service["user"] == "${MIEMIE_RUNTIME_UID:-10001}:${MIEMIE_RUNTIME_GID:-10001}", name
        assert service["read_only"] is True, name
        assert service["init"] is True, name
        assert service["cap_drop"] == ["ALL"], name
        assert "no-new-privileges:true" in service["security_opt"], name
        assert service["stop_grace_period"] == "45s", name
        assert service["tmpfs"] == ["/tmp:rw,noexec,nosuid,size=256m,mode=1777"], name
        logging = service["logging"]
        assert logging["driver"] == "json-file", name
        assert logging["options"] == {"max-size": "10m", "max-file": "5"}, name
        mounts = " ".join(service.get("volumes", []))
        assert "docker.sock" not in mounts, name

    assert services["api"]["ports"] == [
        "${MIEMIE_HOST_BIND:-127.0.0.1}:${MIEMIE_HOST_PORT:-8000}:8000"
    ]
    assert not services["postgres"].get("ports")
    assert not services["redis"].get("ports")
    assert "./backups:/var/lib/miemie/backups" in services["worker-ops"]["volumes"]
    assert "MIEMIE_RUNTIME_UID=10001" in env
    assert "MIEMIE_RUNTIME_GID=10001" in env
    assert "MIEMIE_HOST_BIND=127.0.0.1" in env
    assert "MIEMIE_DATABASE_WRITE_MODE=postgres" in env
    assert "MIEMIE_DATABASE_JSON_FALLBACK_READ=false" in env
    print("self-hosted compose verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
