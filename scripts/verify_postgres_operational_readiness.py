#!/usr/bin/env python3
"""Verify the PostgreSQL-only operational readiness gate contract."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_operational_readiness.sh"


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
    with tempfile.TemporaryDirectory(prefix="miemie-postgres-ops-readiness-") as temp_dir:
        temp = Path(temp_dir)
        artifact_dir = temp / "artifact"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "RUN_ID": "verify-postgres-operational-readiness",
            "ARTIFACT_DIR": str(artifact_dir),
            "TMP_DIR": str(temp / "tmp"),
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
                f"dry-run failed with {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
            )

        status = json.loads((artifact_dir / "status.json").read_text(encoding="utf-8"))
        plan = (artifact_dir / "postgres-operational-readiness-plan.sh").read_text(encoding="utf-8")
        commands = (artifact_dir / "commands.log").read_text(encoding="utf-8")
        results = (artifact_dir / "results.tsv").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert status["confirm"] == "dry-run"
        assert status["backup_restore"] == "skip"
        assert results == "check\tstate\tdetail\n"
        if re.search(r"\b(docker|curl|pg_dump|psql|dropdb|createdb|git fetch|git pull)\b", commands):
            raise AssertionError(f"dry-run executed external command unexpectedly:\n{commands}")

        required_plan_fragments = [
            "CONFIRM_POSTGRES_OPERATIONAL_READINESS=run",
            "POSTGRES_OPS_BACKUP_RESTORE=run",
            "MIEMIE_DATABASE_WRITE_MODE=postgres",
            "MIEMIE_DATABASE_READ_MODE=postgres",
            "MIEMIE_DATABASE_JSON_FALLBACK_READ=false",
            "MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false",
            "MIEMIE_DATABASE_RECONCILE_STRICT=true",
            "local and public /api/health",
            "remaining JSON outside quarantine",
            "fresh PostgreSQL backup",
        ]
        for fragment in required_plan_fragments:
            assert fragment in plan, fragment


def check_static_contract() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        'CONFIRM_POSTGRES_OPERATIONAL_READINESS="${CONFIRM_POSTGRES_OPERATIONAL_READINESS:-dry-run}"',
        'POSTGRES_OPS_BACKUP_RESTORE="${POSTGRES_OPS_BACKUP_RESTORE:-skip}"',
        "BACKUP_MAX_AGE_HOURS",
        "ALLOWED_REMAINING_JSON",
        "MIEMIE_DATABASE_ENABLED true",
        "MIEMIE_DATABASE_WRITE_MODE postgres",
        "MIEMIE_DATABASE_READ_MODE postgres",
        "MIEMIE_DATABASE_JSON_FALLBACK_READ false",
        "MIEMIE_DATABASE_JSON_ARCHIVE_WRITES false",
        "MIEMIE_DATABASE_RECONCILE_STRICT true",
        "MIEMIE_DATABASE_DUAL_WRITE_DOMAINS",
        "MIEMIE_DATABASE_READ_DOMAINS",
        "MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS",
        "scripts/postgres_backup.sh",
        "scripts/postgres_restore_rehearsal.sh",
        "latest-backup.json",
        "remaining-json-outside-quarantine.txt",
        "compose.env.sanitized",
        "docker stats --no-stream",
        "--connect-timeout 10 --max-time 20",
    ]
    for fragment in required_fragments:
        if fragment not in content:
            raise AssertionError(f"missing contract fragment: {fragment}")

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
    check_static_contract()
    print("postgres operational readiness verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
