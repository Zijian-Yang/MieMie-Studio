#!/usr/bin/env python3
"""Verify the production installer contract without mutating the host."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.sh"
LIBRARY = ROOT / "scripts" / "install_lib.sh"


def main() -> int:
    for script in (INSTALLER, LIBRARY):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    with tempfile.TemporaryDirectory(prefix="miemie-installer-") as temp_dir:
        temp = Path(temp_dir)
        artifact = temp / "artifact"
        result = subprocess.run(
            ["bash", str(INSTALLER)],
            cwd=ROOT,
            env={
                **os.environ,
                "MIEMIE_INSTALL_DRY_RUN": "true",
                "MIEMIE_INSTALL_ROOT": str(temp / "install"),
                "MIEMIE_INSTALL_CONFIG_DIR": str(temp / "etc"),
                "MIEMIE_INSTALL_STATE_DIR": str(temp / "state"),
                "MIEMIE_INSTALL_LOG_DIR": str(temp / "log"),
                "MIEMIE_INSTALL_BIN_DIR": str(temp / "bin"),
                "MIEMIE_INSTALL_ARTIFACT_DIR": str(artifact),
            },
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
        status = json.loads((artifact / "status.json").read_text(encoding="utf-8"))
        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert not (temp / "install").exists()
        commands = (artifact / "plan.txt").read_text(encoding="utf-8")
        for stage in (
            "host-preflight",
            "prerequisites",
            "source",
            "configuration",
            "permissions",
            "build",
            "database",
            "administrator",
            "services",
            "health",
            "cli",
        ):
            assert stage in commands

        state = temp / "current.env"
        env_file = temp / "compose.env"
        env_file.write_text(
            "MIEMIE_RUNTIME_GIT_COMMIT=legacy-commit\nMIEMIE_IMAGE=legacy-image\n",
            encoding="utf-8",
        )
        same_commit = "a" * 40
        state.write_text(
            f"commit={same_commit}\nimage=current-image\n"
            f"previous_commit={'b' * 40}\nprevious_image=previous-image\n",
            encoding="utf-8",
        )
        command = (
            f"source {LIBRARY!s}; "
            f"miemie_previous_release_values {state!s} {env_file!s} {same_commit}"
        )
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == f"{'b' * 40}\tprevious-image"

        result = subprocess.run(
            ["bash", "-c", command.rsplit(" ", 1)[0] + f" {'c' * 40}"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == f"{same_commit}\tcurrent-image"

    source = INSTALLER.read_text(encoding="utf-8") + LIBRARY.read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    required = (
        "Ubuntu 22.04",
        "Ubuntu 24.04",
        "Debian 12",
        "MIEMIE_INSTALL_PREREQUISITES",
        "download.docker.com/linux",
        "MIEMIE_PLATFORM_ENCRYPTION_KEY",
        "MIEMIE_POSTGRES_PASSWORD",
        "chmod 600",
        "MIEMIE_RUNTIME_UID",
        "10001:10001",
        "status --porcelain --untracked-files=no",
        "merge-base --is-ancestor",
        "install_source_not_fast_forward",
        "switch --detach",
        "MIEMIE_ADMIN_PASSWORD",
        "admin_args=(bootstrap",
        'admin_args+=(--display-name "$admin_display_name")',
        "app.cli.admin",
        "/api/health",
        "install -m 0755",
        "install -m 0644",
        "miemie_lib.sh",
        "docker compose",
        "previous_commit=",
        "migration_head=",
    )
    for fragment in required:
        assert fragment in source, fragment
    for forbidden in ("set -x", "echo $MIEMIE_ADMIN_PASSWORD", "--password"):
        assert forbidden not in source
    api_section = compose.split("\n  api:\n", 1)[1].split("\n  worker:\n", 1)[0]
    assert "working_dir: /app/backend" in api_section
    print("self-hosted installer verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
