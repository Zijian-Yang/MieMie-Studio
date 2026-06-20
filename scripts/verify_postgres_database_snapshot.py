#!/usr/bin/env python3
"""Verify PostgreSQL database snapshot script contract."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_database_snapshot.sh"


def main() -> int:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], cwd=ROOT_DIR, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr)

    with tempfile.TemporaryDirectory(prefix="miemie-postgres-snapshot-") as temp_dir:
        artifact = Path(temp_dir) / "artifact"
        env = {
            **os.environ,
            "RUN_ID": "verify-postgres-database-snapshot",
            "ARTIFACT_DIR": str(artifact),
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
        plan = (artifact / "postgres-database-snapshot-plan.sh").read_text(encoding="utf-8")
        commands = (artifact / "commands.log").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        if re.search(r"\b(docker|psql|pg_dump|dropdb|createdb)\b", commands):
            raise AssertionError(f"dry-run executed external command unexpectedly:\n{commands}")

        required_plan_fragments = [
            "PostgreSQL database snapshot is read-only",
            "pg_stat_activity",
            "pg_stat_user_tables",
            "pg_locks",
            "CONFIRM_POSTGRES_DATABASE_SNAPSHOT=run",
        ]
        for fragment in required_plan_fragments:
            assert fragment in plan, fragment

    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        "pg_database_size",
        "to_regclass('public.' || name)",
        "pg_stat_user_tables",
        "pg_stat_user_indexes",
        "pg_stat_activity",
        "pg_locks",
        "long_transaction_count",
        "waiting_lock_count",
        "missing expected tables",
        "video_studio_tasks",
        "audio_studio_tasks",
        "sessions",
        "--csv",
    ]
    for fragment in required_fragments:
        if fragment not in content:
            raise AssertionError(f"missing contract fragment: {fragment}")

    forbidden_fragments = [
        "pg_dump",
        "dropdb",
        "createdb",
        "delete from",
        "truncate",
        "update ",
        "insert into",
        "alter table",
        "create table",
        "docker compose up",
        "git reset --hard",
    ]
    lower = content.lower()
    for fragment in forbidden_fragments:
        if fragment in lower:
            raise AssertionError(f"forbidden mutating fragment: {fragment}")

    print("postgres database snapshot verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
