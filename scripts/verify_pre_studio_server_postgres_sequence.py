#!/usr/bin/env python3
"""Verify the server-side PostgreSQL sequence wrapper without touching Docker."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "pre_studio_server_postgres_sequence.sh"


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
    with tempfile.TemporaryDirectory(prefix="miemie-server-sequence-") as temp_dir:
        temp = Path(temp_dir)
        artifact_dir = temp / "artifact"
        tmp_dir = temp / "tmp"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "RUN_ID": "verify-server-sequence",
            "ARTIFACT_DIR": str(artifact_dir),
            "TMP_DIR": str(tmp_dir),
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
        commands = (artifact_dir / "commands.log").read_text(encoding="utf-8")
        plan = (artifact_dir / "server-sequence-plan.sh").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert status["confirm"] == "dry-run"
        assert "set CONFIRM_SERVER_SEQUENCE=run" in status["reason"]
        assert "git merge --ff-only origin/pre" in plan
        assert "live-data-gate" in plan
        assert "postgres_staging_live_data_gate.sh" in plan
        assert "CONFIRM_STAGING_SEQUENCE=run" in plan
        assert "scripts/postgres_staging_video_task_sequence.sh" in plan
        if re.search(r"\b(docker|curl|ssh|scp|nc|git fetch|git merge)\b", commands):
            raise AssertionError(f"dry-run executed mutable command unexpectedly:\n{commands}")


def check_safety_contract() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        'CONFIRM_SERVER_SEQUENCE="${CONFIRM_SERVER_SEQUENCE:-dry-run}"',
        'ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/validation-artifacts/$RUN_ID}"',
        "git merge --ff-only",
        "live-data-gate",
        "postgres_staging_live_data_gate.sh",
        'failed "sync"',
        "CONFIRM_STAGING_SEQUENCE=run",
        "verify_server_context",
        "missing compose.env",
        "docker-compose.pre.override.yml",
        "validation-artifacts",
        'write_status "dry_run" "planned"',
    ]
    for fragment in required_fragments:
        if fragment not in content:
            raise AssertionError(f"missing safety fragment: {fragment}")

    forbidden_fragments = [
        "git reset --hard",
        "git checkout --",
        "docker system prune",
        "ssh ",
        "scp ",
    ]
    for fragment in forbidden_fragments:
        if fragment in content:
            raise AssertionError(f"forbidden fragment: {fragment}")


def main() -> int:
    run_shell_syntax_check()
    run_dry_run_contract()
    check_safety_contract()
    print("pre-studio server postgres sequence verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
