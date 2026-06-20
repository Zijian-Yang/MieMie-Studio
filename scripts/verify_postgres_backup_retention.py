#!/usr/bin/env python3
"""Verify PostgreSQL backup retention script contract."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_backup_retention.sh"


def touch_backup(path: Path, age_days: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("-- synthetic backup\n", encoding="utf-8")
    timestamp = time.time() - age_days * 86400
    os.utime(path, (timestamp, timestamp))


def run_retention(temp: Path, confirm: str = "dry-run") -> tuple[dict, str]:
    artifact = temp / f"artifact-{confirm}"
    env = {
        **os.environ,
        "RUN_ID": f"verify-retention-{confirm}",
        "ARTIFACT_DIR": str(artifact),
        "BACKUP_DIR": str(temp / "backups"),
        "RETENTION_DAYS": "14",
        "MIN_KEEP": "2",
        "CONFIRM_POSTGRES_BACKUP_RETENTION": confirm,
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
        raise AssertionError(f"retention failed: {result.returncode}\n{result.stdout}\n{result.stderr}")
    status = json.loads((artifact / "status.json").read_text(encoding="utf-8"))
    manifest = (artifact / "postgres-backup-retention-manifest.tsv").read_text(encoding="utf-8")
    return status, manifest


def main() -> int:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], cwd=ROOT_DIR, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr)

    with tempfile.TemporaryDirectory(prefix="miemie-backup-retention-") as temp_dir:
        temp = Path(temp_dir)
        for index, age in enumerate([0, 1, 20, 21], start=1):
            touch_backup(temp / "backups" / f"miemie-postgres-202606{index:02d}-010101.sql", age)

        status, manifest = run_retention(temp)
        assert status["state"] == "dry_run"
        assert status["delete_candidate_count"] == 2
        assert "delete_candidate" in manifest
        assert len(list((temp / "backups").glob("*.sql"))) == 4

        status, manifest = run_retention(temp, "prune")
        assert status["state"] == "passed"
        assert status["deleted_count"] == 2
        assert "deleted" in manifest
        assert len(list((temp / "backups").glob("*.sql"))) == 2

    print("postgres backup retention verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
