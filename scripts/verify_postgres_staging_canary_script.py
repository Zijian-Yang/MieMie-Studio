#!/usr/bin/env python3
"""Verify the staging PostgreSQL canary shell script without loading the app."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_staging_video_task_canary.sh"


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


def run_missing_env_precheck() -> None:
    with tempfile.TemporaryDirectory(prefix="miemie-canary-verify-") as temp_dir:
        temp = Path(temp_dir)
        artifact_dir = temp / "artifact"
        tmp_dir = temp / "tmp"
        missing_env = temp / "missing-compose.env"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "MODE": "audit",
            "RUN_ID": "verify-missing-compose-env",
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

        status_path = artifact_dir / "status.json"
        commands_path = artifact_dir / "commands.log"
        status = json.loads(status_path.read_text(encoding="utf-8"))
        commands = commands_path.read_text(encoding="utf-8")

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

    for index, block in enumerate(blocks, start=1):
        compile(block, f"{SCRIPT}:heredoc:{index}", "exec")


def check_safety_contract() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        'MODE="${1:-${MODE:-audit}}"',
        "ensure_preconditions",
        'set_env_value MIEMIE_DATABASE_ENABLED false',
        'set_env_value MIEMIE_DATABASE_DUAL_WRITE_DOMAINS "$DOMAIN"',
        'set_env_value MIEMIE_DATABASE_READ_DOMAINS ""',
        'set_env_value MIEMIE_DATABASE_READ_DOMAINS "$DOMAIN"',
        "read-switch-canary",
        "rollback-read-switch",
        "run_read_switch_storage_canary",
        "run_rollback_read_storage_canary",
        '"expected_read_source": "postgres"',
        '"expected_read_source": "json"',
        "storage.save_video_studio_task(task)",
        "storage._save_video_studio_task_to_file(json_task)",
        "storage._delete_video_studio_task_from_file(task_id)",
        "/api/video-studio/preview-payload",
        "POSTGRES_PASSWORD",
        "<redacted>",
    ]
    for fragment in required_fragments:
        if fragment not in content:
            raise AssertionError(f"missing safety fragment: {fragment}")

    forbidden_patterns = [
        r"\$url/api/video-studio[\"']?\s*\)",
        r"\$url/api/video-studio[\"']?\s*$",
        r"/api/video-studio/generate",
    ]
    for pattern in forbidden_patterns:
        if re.search(pattern, content, re.MULTILINE):
            raise AssertionError(f"forbidden real video-studio submission pattern: {pattern}")


def main() -> int:
    run_shell_syntax_check()
    run_missing_env_precheck()
    compile_embedded_python_blocks()
    check_safety_contract()
    print("postgres staging canary script verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
