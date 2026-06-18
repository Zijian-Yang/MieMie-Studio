#!/usr/bin/env python3
"""Verify the remote final PostgreSQL-only exit sequence wrapper without network access."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "pre_studio_remote_postgres_final_exit_sequence.sh"


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
    with tempfile.TemporaryDirectory(prefix="miemie-remote-final-exit-verify-") as temp_dir:
        temp = Path(temp_dir)
        artifact_dir = temp / "artifact"
        tmp_dir = temp / "tmp"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "RUN_ID": "verify-remote-final-exit",
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
        remote_command = (artifact_dir / "remote-command.sh").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert status["confirm"] == "dry-run"
        assert status["rollback_on_failure"] == "true"
        assert "set CONFIRM_REMOTE_FINAL_EXIT_SEQUENCE=run" in status["reason"]
        assert "git merge --ff-only origin/pre" in remote_command
        assert "CONFIRM_SERVER_FINAL_EXIT_SEQUENCE=run" in remote_command
        assert "SERVER_SYNC=none" in remote_command
        assert "FINAL_EXIT_ROLLBACK_ON_FAILURE=true" in remote_command
        assert "scripts/pre_studio_server_postgres_final_exit_sequence.sh" in remote_command
        assert "CONFIRM_SERVER_SEQUENCE=run" not in remote_command
        assert "scripts/pre_studio_server_postgres_sequence.sh" not in remote_command
        if re.search(r"\b(ssh|scp|dig|route|nc|curl)\b", commands):
            raise AssertionError(f"dry-run executed network command unexpectedly:\n{commands}")


def check_safety_contract() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        'CONFIRM_REMOTE_FINAL_EXIT_SEQUENCE="${CONFIRM_REMOTE_FINAL_EXIT_SEQUENCE:-dry-run}"',
        'LOCAL_PREFLIGHT_SCRIPT="${LOCAL_PREFLIGHT_SCRIPT:-$ROOT_DIR/scripts/pre_studio_connectivity_preflight.sh}"',
        'REMOTE_RUNNER="${REMOTE_RUNNER:-scripts/pre_studio_server_postgres_final_exit_sequence.sh}"',
        'FINAL_EXIT_ROLLBACK_ON_FAILURE="${FINAL_EXIT_ROLLBACK_ON_FAILURE:-true}"',
        "run_local_preflight",
        "git merge --ff-only",
        "REMOTE_SYNC",
        "CONFIRM_SERVER_FINAL_EXIT_SEQUENCE=run",
        "SERVER_SYNC=none",
        "FINAL_EXIT_ROLLBACK_ON_FAILURE",
        "pre_studio_server_postgres_final_exit_sequence.sh",
        "BatchMode=yes",
        "ConnectTimeout",
        "PULL_REMOTE_ARTIFACTS",
        "validation-artifacts",
        'write_status "blocked" "preflight"',
    ]
    for fragment in required_fragments:
        if fragment not in content:
            raise AssertionError(f"missing safety fragment: {fragment}")
    forbidden_fragments = [
        "git reset --hard",
        "git checkout --",
        "docker system prune",
    ]
    for fragment in forbidden_fragments:
        if fragment in content:
            raise AssertionError(f"forbidden destructive fragment: {fragment}")


def main() -> int:
    run_shell_syntax_check()
    run_dry_run_contract()
    check_safety_contract()
    print("pre-studio remote postgres final exit sequence verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
