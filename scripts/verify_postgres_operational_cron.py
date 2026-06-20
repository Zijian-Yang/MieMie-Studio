#!/usr/bin/env python3
"""Verify PostgreSQL operational cron installer dry-run contract."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_install_operational_cron.sh"


def main() -> int:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], cwd=ROOT_DIR, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr)

    with tempfile.TemporaryDirectory(prefix="miemie-operational-cron-") as temp_dir:
        artifact = Path(temp_dir) / "artifact"
        cron_target = Path(temp_dir) / "miemie-postgres-ops"
        env = {
            **os.environ,
            "RUN_ID": "verify-operational-cron",
            "ARTIFACT_DIR": str(artifact),
            "CRON_FILE": str(cron_target),
            "INSTALL_ROOT": "/opt/miemie-pre",
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
        preview = (artifact / "miemie-postgres-ops.cron").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert not cron_target.exists()
        required = [
            "/etc/miemie-postgres-ops-alert.env",
            "set -a; .",
            "POSTGRES_OPS_TRIGGER=cron",
            "CONFIRM_POSTGRES_OPERATIONAL_READINESS=run",
            "POSTGRES_OPS_BACKUP_RESTORE=run",
            "scripts/postgres_operational_readiness.sh",
            "CONFIRM_POSTGRES_BACKUP_RETENTION=prune",
            "scripts/postgres_backup_retention.sh",
            "CONFIRM_POSTGRES_DATABASE_SNAPSHOT=run",
            "scripts/postgres_database_snapshot.sh",
            "postgres-operational-readiness-cron.log",
            "postgres-backup-retention-cron.log",
            "postgres-database-snapshot-cron.log",
        ]
        for fragment in required:
            assert fragment in preview, fragment

    print("postgres operational cron verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
