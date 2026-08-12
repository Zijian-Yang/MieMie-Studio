#!/usr/bin/env python3
"""Verify deploy_doctor without mutating the host or requiring network access."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "deploy_doctor.sh"


def run_shell_syntax_check() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=ROOT_DIR,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)


def run_dry_run_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="miemie-deploy-doctor-") as temp_dir:
        temp = Path(temp_dir)
        artifact_dir = temp / "artifact"
        tmp_dir = temp / "tmp"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "RUN_ID": "verify-deploy-doctor",
            "ARTIFACT_DIR": str(artifact_dir),
            "TMP_DIR": str(tmp_dir),
            "MIEMIE_DEPLOY_DOCTOR_DRY_RUN": "true",
        }
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT_DIR,
            check=False,
            text=True,
            capture_output=True,
            env=env,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"expected dry-run to exit 0, got {result.returncode}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )
        status = json.loads((artifact_dir / "status.json").read_text(encoding="utf-8"))
        results = (artifact_dir / "results.tsv").read_text(encoding="utf-8")
        commands = (artifact_dir / "commands.log").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert status["counts"]["passed"] == 1
        assert "dry_run\tpassed\tno checks executed" in results
        if re.search(r"\b(docker|curl|npm|pip|apt-get|brew|git fetch|git pull)\b", commands):
            raise AssertionError(f"dry-run executed external command unexpectedly:\n{commands}")


def check_safety_contract() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        'DOCTOR_PROFILE="${DOCTOR_PROFILE:-all}"',
        'MIEMIE_DEPLOY_DOCTOR_DRY_RUN="${MIEMIE_DEPLOY_DOCTOR_DRY_RUN:-false}"',
        "compose.env.example",
        "replace-with-strong-password",
        "replace-with-git-commit",
        "replace-with-urlsafe-base64-32-byte-key",
        "compose_env:platform_encryption_key",
        "backend/data/config.json",
        "backend/data/users.json",
        "backend/data/sessions.json",
        "MIEMIE_HOST_BIND exposes app port directly",
        "docker compose --env-file",
        "config -q",
        "MIEMIE_DEPLOY_DOCTOR_RUN_DOCKER_INFO",
        "compose.env.sanitized",
    ]
    for fragment in required_fragments:
        if fragment not in content:
            raise AssertionError(f"missing safety fragment: {fragment}")

    forbidden_fragments = [
        "apt-get install",
        "brew install",
        "npm install",
        "pip install",
        "docker compose up",
        "docker system prune",
        "git reset --hard",
    ]
    for fragment in forbidden_fragments:
        if fragment in content:
            raise AssertionError(f"forbidden mutating fragment: {fragment}")


def main() -> int:
    run_shell_syntax_check()
    run_dry_run_contract()
    check_safety_contract()
    print("deploy doctor verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
