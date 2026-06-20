#!/usr/bin/env python3
"""Verify PostgreSQL operational cron sequence runner contract."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_operational_cron_sequence.sh"


def main() -> int:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], cwd=ROOT_DIR, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr)

    with tempfile.TemporaryDirectory(prefix="miemie-cron-sequence-") as temp_dir:
        temp = Path(temp_dir)
        artifact = temp / "artifact"
        validation_root = temp / "validation-artifacts"
        env = {
            **os.environ,
            "RUN_ID": "verify-postgres-operational-cron-sequence",
            "ARTIFACT_DIR": str(artifact),
            "VALIDATION_ROOT": str(validation_root),
            "ALERT_ENV_FILE": str(temp / "missing-alert-env"),
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
            raise AssertionError(f"dry-run failed: {result.returncode}\n{result.stdout}\n{result.stderr}")

        status = json.loads((artifact / "status.json").read_text(encoding="utf-8"))
        plan = (artifact / "postgres-operational-cron-sequence-plan.sh").read_text(encoding="utf-8")
        summary = (artifact / "postgres-operational-cron-sequence-summary.tsv").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert "step\tstate\trun_id\tartifact_dir\texit_code" in summary

        forbidden_dry_run = [
            "docker compose",
            "psql",
            "pg_dump",
            "dropdb",
            "createdb",
            "postgres_operational_readiness.sh",
            "postgres_backup_retention.sh",
            "postgres_database_snapshot.sh",
            "postgres_operational_cron_evidence.sh",
        ]
        for fragment in forbidden_dry_run:
            if fragment in result.stdout or fragment in result.stderr:
                raise AssertionError(f"dry-run executed or printed subcommand unexpectedly: {fragment}")

        required_plan_fragments = [
            "PostgreSQL operational cron sequence gate",
            "CONFIRM_POSTGRES_CRON_SEQUENCE=run",
            "operational readiness",
            "backup retention prune",
            "read-only database snapshot",
            "CRON_EVIDENCE_STRICT_WAIT=true",
            "CRON_EVIDENCE_NOT_BEFORE",
        ]
        for fragment in required_plan_fragments:
            assert fragment in plan, fragment

    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        "postgres_operational_readiness.sh",
        "POSTGRES_OPS_BACKUP_RESTORE=run",
        "postgres_backup_retention.sh",
        "CONFIRM_POSTGRES_BACKUP_RETENTION=prune",
        "postgres_database_snapshot.sh",
        "CONFIRM_POSTGRES_DATABASE_SNAPSHOT=run",
        "postgres_operational_cron_evidence.sh",
        "CRON_EVIDENCE_NOT_BEFORE",
        "CRON_EVIDENCE_STRICT_WAIT=true",
        "verify_evidence_passed",
        "ALERT_ENV_FILE",
    ]
    for fragment in required_fragments:
        if fragment not in content:
            raise AssertionError(f"missing contract fragment: {fragment}")

    forbidden_fragments = [
        "git reset --hard",
        "docker compose down",
        "docker compose rm",
        "rm -rf",
        "apt install",
        "yum install",
        "apk add",
    ]
    lower = content.lower()
    for fragment in forbidden_fragments:
        if re.search(re.escape(fragment), lower):
            raise AssertionError(f"forbidden fragment: {fragment}")

    print("postgres operational cron sequence verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
