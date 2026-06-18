#!/usr/bin/env python3
"""Verify the server-side final PostgreSQL-only exit sequence wrapper."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "pre_studio_server_postgres_final_exit_sequence.sh"


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
    with tempfile.TemporaryDirectory(prefix="miemie-server-final-exit-") as temp_dir:
        temp = Path(temp_dir)
        artifact_dir = temp / "artifact"
        tmp_dir = temp / "tmp"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "RUN_ID": "verify-server-final-exit",
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
        plan = (artifact_dir / "server-final-exit-sequence-plan.sh").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert status["confirm"] == "dry-run"
        assert status["rollback_on_failure"] == "true"
        assert "set CONFIRM_SERVER_FINAL_EXIT_SEQUENCE=run" in status["reason"]

        required_plan_fragments = [
            "CONFIRM_SERVER_SEQUENCE=run",
            "pre_studio_server_postgres_sequence.sh",
            "SEQUENCE_ARTIFACT_DIR=",
            "CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY=run",
            "postgres_apply_final_json_exit_policy.sh",
            "CONFIRM_POST_JSON_EXIT_VALIDATION=run",
            "postgres_post_json_exit_validation.sh",
            "CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY=run",
            "postgres_rollback_final_json_exit_policy.sh",
            "compose.env.before-final-json-exit",
        ]
        for fragment in required_plan_fragments:
            assert fragment in plan, fragment

        if re.search(r"\b(docker|curl|ssh|scp|nc|git fetch|git merge|k6)\b", commands):
            raise AssertionError(f"dry-run executed mutable command unexpectedly:\n{commands}")


def check_static_safety_contract() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        'CONFIRM_SERVER_FINAL_EXIT_SEQUENCE="${CONFIRM_SERVER_FINAL_EXIT_SEQUENCE:-dry-run}"',
        'FINAL_EXIT_ROLLBACK_ON_FAILURE="${FINAL_EXIT_ROLLBACK_ON_FAILURE:-true}"',
        'ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/validation-artifacts/$RUN_ID}"',
        "pre_studio_server_postgres_sequence.sh",
        "postgres_apply_final_json_exit_policy.sh",
        "postgres_post_json_exit_validation.sh",
        "postgres_rollback_final_json_exit_policy.sh",
        "CONFIRM_SERVER_SEQUENCE=run",
        "CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY=run",
        "CONFIRM_POST_JSON_EXIT_VALIDATION=run",
        "CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY=run",
        "rollback_on_failure",
        "find_rollback_backup",
        "run_rollback",
        "check_status_state",
        'write_status "passed" "done"',
    ]
    for fragment in required_fragments:
        if fragment not in content:
            raise AssertionError(f"missing safety fragment: {fragment}")

    forbidden_fragments = [
        "git reset --hard",
        "git checkout --",
        "docker system prune",
        "rm -rf",
        "ssh ",
        "scp ",
    ]
    for fragment in forbidden_fragments:
        if fragment in content:
            raise AssertionError(f"forbidden fragment: {fragment}")


def main() -> int:
    run_shell_syntax_check()
    run_dry_run_contract()
    check_static_safety_contract()
    print("pre-studio server postgres final exit sequence verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
