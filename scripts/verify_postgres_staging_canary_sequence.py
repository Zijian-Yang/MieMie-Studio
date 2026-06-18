#!/usr/bin/env python3
"""Verify the staging PostgreSQL canary sequence runner without Docker."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_staging_video_task_sequence.sh"


EXPECTED_MODES = [
    "audit",
    "roll-runtime",
    "live-data-gate",
    "all-domain-dual-write-canary",
    "all-domain-read-switch-canary",
    "all-domain-rollback-read-switch",
    "all-domain-primary-write-canary",
    "all-domain-rollback-primary-write",
]


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
    with tempfile.TemporaryDirectory(prefix="miemie-sequence-verify-") as temp_dir:
        temp = Path(temp_dir)
        artifact_dir = temp / "artifact"
        tmp_dir = temp / "tmp"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "RUN_ID": "verify-staging-sequence",
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
        sequence = (artifact_dir / "sequence.txt").read_text(encoding="utf-8")
        results = (artifact_dir / "results.tsv").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert status["confirm"] == "dry-run"
        assert "set CONFIRM_STAGING_SEQUENCE=run to execute" in status["reason"]
        assert results == "index\tmode\texit_code\tstate\tartifact_dir\n"

        for index, mode in enumerate(EXPECTED_MODES, start=1):
            assert f"{index:02d} {mode}" in sequence
            assert mode in status["sequence"]

        if re.search(r"\bdocker\b", commands, re.IGNORECASE):
            raise AssertionError(f"dry-run touched docker unexpectedly:\n{commands}")
        if "postgres_staging_video_task_canary.sh" in commands:
            raise AssertionError(f"dry-run executed canary unexpectedly:\n{commands}")
        if "postgres_staging_all_domain_canary.sh" in commands:
            raise AssertionError(f"dry-run executed all-domain canary unexpectedly:\n{commands}")


def check_safety_contract() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        'CONFIRM_STAGING_SEQUENCE="${CONFIRM_STAGING_SEQUENCE:-dry-run}"',
        'if [[ "$CONFIRM_STAGING_SEQUENCE" != "run" ]]',
        "set CONFIRM_STAGING_SEQUENCE=run to execute",
        "stage_state_for_exit",
        "LIVE_DATA_GATE_SCRIPT",
        "ALL_DOMAIN_CANARY_SCRIPT",
        "live-data-gate",
        "all-domain-rollback-primary-write",
        "all-domain-primary-write-canary",
        "all-domain-rollback-read-switch",
        'if [[ "$mode" == "live-data-gate" ]]',
        'elif [[ "$mode" == all-domain-* ]]',
        "bash \"$LIVE_DATA_GATE_SCRIPT\"",
        "bash \"$ALL_DOMAIN_CANARY_SCRIPT\"",
        "CONFIRM_ALL_DOMAIN_CANARY=run",
        "MODE=\"$mode\"",
        "ARTIFACT_DIR=\"$stage_dir\"",
        "TMP_DIR=\"$stage_tmp\"",
        "write_status \"$state\" \"$mode\"",
    ]
    for fragment in required_fragments:
        if fragment not in content:
            raise AssertionError(f"missing safety fragment: {fragment}")


def main() -> int:
    run_shell_syntax_check()
    run_dry_run_contract()
    check_safety_contract()
    print("postgres staging canary sequence verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
