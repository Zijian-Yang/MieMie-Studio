#!/usr/bin/env python3
"""Verify the staging PostgreSQL live data gate without touching Docker."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_staging_live_data_gate.sh"

DOMAINS = [
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
    with tempfile.TemporaryDirectory(prefix="miemie-live-data-gate-") as temp_dir:
        temp = Path(temp_dir)
        artifact_dir = temp / "artifact"
        tmp_dir = temp / "tmp"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "RUN_ID": "verify-live-data-gate",
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
        plan = (artifact_dir / "live-data-gate-plan.sh").read_text(encoding="utf-8")
        domains = (artifact_dir / "domains.txt").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert status["confirm"] == "dry-run"
        assert "set CONFIRM_LIVE_DATA_GATE=run" in status["reason"]
        assert "alembic upgrade head" in plan
        assert "postgres_backup.sh" in plan
        assert "postgres_restore_rehearsal.sh" in plan
        assert "MIEMIE_DATABASE_ENABLED=true" in plan
        assert "MIEMIE_DATABASE_WRITE_MODE=file" in plan
        assert "MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=" in plan
        assert "MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=" in plan
        assert "MIEMIE_DATABASE_READ_DOMAINS=" in plan

        for domain in DOMAINS:
            assert domain in domains
            assert f"postgres_backfill_{domain}.py" in plan
            assert f"postgres_reconcile_{domain}.py" in plan

        if re.search(r"\b(docker|curl|ssh|scp|nc|git fetch|git merge)\b", commands):
            raise AssertionError(f"dry-run executed mutable command unexpectedly:\n{commands}")


def check_safety_contract() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        'CONFIRM_LIVE_DATA_GATE="${CONFIRM_LIVE_DATA_GATE:-dry-run}"',
        'ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r64-staging-live-data-gate}"',
        "write_plan",
        "verify_server_context",
        "expand_database_url",
        "resolve_postgres_container_host",
        "resolve_maintenance_database_url",
        "docker inspect",
        "@postgres:",
        "postgres_cleanup_canary_user_config_residue.py",
        "cleanup-canary-user-config",
        "alembic-upgrade-head",
        "postgres_backfill_${domain}.py",
        "postgres_reconcile_${domain}.py",
        "postgres_backup.sh",
        "postgres_restore_rehearsal.sh",
        "MIEMIE_DATABASE_ENABLED=true",
        "MIEMIE_DATABASE_WRITE_MODE=file",
        "MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=",
        "MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=",
        "MIEMIE_DATABASE_READ_DOMAINS=",
        'write_status "dry_run" "planned"',
    ]
    for fragment in required_fragments:
        if fragment not in content:
            raise AssertionError(f"missing safety fragment: {fragment}")

    forbidden_fragments = [
        "git reset --hard",
        "git checkout --",
        "docker system prune",
        "MIEMIE_DATABASE_WRITE_MODE=postgres",
        "MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=video_studio_tasks",
    ]
    for fragment in forbidden_fragments:
        if fragment in content:
            raise AssertionError(f"forbidden fragment: {fragment}")


def main() -> int:
    run_shell_syntax_check()
    run_dry_run_contract()
    check_safety_contract()
    print("postgres staging live data gate verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
