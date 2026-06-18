#!/usr/bin/env python3
"""Verify the all-domain staging PostgreSQL canary without Docker or app imports."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_staging_all_domain_canary.sh"
SEQUENCE_SCRIPT = ROOT_DIR / "scripts" / "postgres_staging_video_task_sequence.sh"
READINESS_SCRIPT = ROOT_DIR / "scripts" / "postgres_final_cutover_readiness.py"

EXPECTED_DOMAINS = [
    "video_studio_tasks",
    "studio_tasks",
    "projects",
    "media_metadata",
    "project_entities",
    "benchmark_records",
    "user_config",
    "sessions",
    "audio_studio",
]

EXPECTED_ALL_DOMAIN_STAGES = [
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
    with tempfile.TemporaryDirectory(prefix="miemie-all-domain-canary-") as temp_dir:
        temp = Path(temp_dir)
        artifact_dir = temp / "artifact"
        tmp_dir = temp / "tmp"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "RUN_ID": "verify-all-domain-canary-dry-run",
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
        plan = (artifact_dir / "all-domain-canary-plan.sh").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert status["mode"] == "all-domain-dual-write-canary"
        assert status["confirm"] == "dry-run"
        assert status["domains"].split() == EXPECTED_DOMAINS

        for stage in EXPECTED_ALL_DOMAIN_STAGES:
            assert stage in plan
        for domain in EXPECTED_DOMAINS:
            assert domain in plan
            assert domain in status["domains"]

        if re.search(r"\b(docker|curl|ssh|scp|nc|git fetch|git merge)\b", commands):
            raise AssertionError(f"dry-run executed mutable command unexpectedly:\n{commands}")


def run_missing_env_precheck() -> None:
    with tempfile.TemporaryDirectory(prefix="miemie-all-domain-canary-env-") as temp_dir:
        temp = Path(temp_dir)
        artifact_dir = temp / "artifact"
        tmp_dir = temp / "tmp"
        missing_env = temp / "missing-compose.env"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "MODE": "all-domain-dual-write-canary",
            "CONFIRM_ALL_DOMAIN_CANARY": "run",
            "RUN_ID": "verify-all-domain-canary-missing-env",
            "ARTIFACT_DIR": str(artifact_dir),
            "TMP_DIR": str(tmp_dir),
            "ENV_FILE": str(missing_env),
        }
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT_DIR,
            check=False,
            text=True,
            capture_output=True,
            env=env,
        )
        if result.returncode != 2:
            raise AssertionError(
                f"expected missing env precheck to exit 2, got {result.returncode}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )
        status = json.loads((artifact_dir / "status.json").read_text(encoding="utf-8"))
        commands = (artifact_dir / "commands.log").read_text(encoding="utf-8")
        assert status["state"] == "blocked"
        assert status["stage"] == "precheck"
        assert status["reason"] == f"missing {missing_env}"
        if re.search(r"\bdocker\b", commands, re.IGNORECASE):
            raise AssertionError(f"precheck touched docker unexpectedly:\n{commands}")


def compile_embedded_python_blocks() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    blocks: list[str] = []
    current: list[str] | None = None
    for line in content.splitlines():
        if current is None and "<<'PY'" in line:
            current = []
            continue
        if current is not None and line == "PY":
            blocks.append("\n".join(current))
            current = None
            continue
        if current is not None:
            current.append(line)
    if current is not None:
        raise AssertionError("unterminated embedded Python heredoc")
    assert blocks, "expected embedded provider-free canary Python block"
    for index, block in enumerate(blocks, start=1):
        compile(block, f"{SCRIPT}:heredoc:{index}", "exec")


def check_safety_contract() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    for fragment in [
        'MODE="${1:-${MODE:-all-domain-dual-write-canary}}"',
        'CONFIRM_ALL_DOMAIN_CANARY="${CONFIRM_ALL_DOMAIN_CANARY:-dry-run}"',
        "ALL_DOMAINS",
        "all-domain-dual-write-canary",
        "all-domain-read-switch-canary",
        "all-domain-rollback-read-switch",
        "all-domain-primary-write-canary",
        "all-domain-rollback-primary-write",
        "run_provider_free_canary",
        "-w",
        "/app/backend",
        "StorageService",
        "UserService",
        "ConfigManager",
        "save_project",
        "save_studio_task",
        "save_video_studio_task",
        "save_audio_studio_task",
        "save_image_benchmark_dataset",
        "save_voice_profile",
        "register(",
        "login(",
        "logout(",
        "MIEMIE_DATABASE_DUAL_WRITE_DOMAINS",
        "MIEMIE_DATABASE_READ_DOMAINS",
        "MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS",
        "<redacted>",
    ]:
        if fragment not in content:
            raise AssertionError(f"missing all-domain canary fragment: {fragment}")

    for forbidden in [
        "dashscope",
        "/api/video-studio/generate",
        "/api/studio/generate",
        "DASHSCOPE_API_KEY",
        "ALIYUN_ACCESS_KEY_SECRET",
    ]:
        if forbidden in content:
            raise AssertionError(f"forbidden provider fragment: {forbidden}")


def check_sequence_uses_all_domain_canary() -> None:
    content = SEQUENCE_SCRIPT.read_text(encoding="utf-8")
    for stage in EXPECTED_ALL_DOMAIN_STAGES:
        if stage not in content:
            raise AssertionError(f"sequence missing all-domain stage: {stage}")
    if "ALL_DOMAIN_CANARY_SCRIPT" not in content:
        raise AssertionError("sequence runner does not expose ALL_DOMAIN_CANARY_SCRIPT")
    if "bash \"$ALL_DOMAIN_CANARY_SCRIPT\"" not in content:
        raise AssertionError("sequence runner does not execute all-domain canary script")


def check_readiness_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="miemie-readiness-after-all-domain-") as temp_dir:
        artifact_dir = Path(temp_dir) / "artifact"
        result = subprocess.run(
            [
                "python3",
                str(READINESS_SCRIPT),
                "--artifact-dir",
                str(artifact_dir),
                "--run-id",
                "verify-after-all-domain-canary",
            ],
            cwd=ROOT_DIR,
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        status = json.loads((artifact_dir / "status.json").read_text(encoding="utf-8"))
        summary = json.loads(
            (artifact_dir / "final-cutover-readiness.summary.json").read_text(encoding="utf-8")
        )
        assert status["state"] == "ready_for_final_cutover_sequence"
        assert status["next_recommended_step"] == "run_server_final_cutover_sequence"
        checks = {item["name"]: item for item in summary["checks"]}
        assert checks["app_canary_domain_coverage"]["state"] == "passed"
        assert checks["app_canary_domain_coverage"]["missing_domains"] == []
        assert checks["app_canary_domain_coverage"]["covered_domains"] == EXPECTED_DOMAINS


def main() -> int:
    run_shell_syntax_check()
    run_dry_run_contract()
    run_missing_env_precheck()
    compile_embedded_python_blocks()
    check_safety_contract()
    check_sequence_uses_all_domain_canary()
    check_readiness_contract()
    print("postgres staging all-domain canary verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
