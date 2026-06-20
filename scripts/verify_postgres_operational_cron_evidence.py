#!/usr/bin/env python3
"""Verify PostgreSQL operational cron evidence checker contract."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_operational_cron_evidence.sh"


def run_script(temp: Path, validation_root: Path, extra_env: dict[str, str] | None = None) -> tuple[int, dict]:
    artifact = temp / f"artifact-{len(list(temp.glob('artifact-*')))}"
    cron_file = temp / "miemie-postgres-ops.cron"
    cron_file.write_text("# synthetic cron\n", encoding="utf-8")
    env = {
        **os.environ,
        "RUN_ID": f"verify-cron-evidence-{len(list(temp.iterdir()))}",
        "ARTIFACT_DIR": str(artifact),
        "VALIDATION_ROOT": str(validation_root),
        "CRON_FILE": str(cron_file),
        "CRON_SERVICE_STATE_OVERRIDE": "active",
        "CONFIRM_POSTGRES_CRON_EVIDENCE": "check",
        **(extra_env or {}),
    }
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT_DIR,
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
    status = json.loads((artifact / "status.json").read_text(encoding="utf-8"))
    return result.returncode, status


def write_status(root: Path, dirname: str, state: str) -> None:
    target = root / dirname
    target.mkdir(parents=True, exist_ok=True)
    (target / "status.json").write_text(
        json.dumps(
            {
                "run_id": dirname,
                "state": state,
                "stage": "done",
                "reason": "",
                "updated_at": "2026-06-20T08:00:00Z",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], cwd=ROOT_DIR, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr)

    with tempfile.TemporaryDirectory(prefix="miemie-cron-evidence-") as temp_dir:
        temp = Path(temp_dir)
        validation_root = temp / "validation-artifacts"

        artifact = temp / "dry-run-artifact"
        env = {
            **os.environ,
            "RUN_ID": "verify-cron-evidence-dry-run",
            "ARTIFACT_DIR": str(artifact),
            "VALIDATION_ROOT": str(validation_root),
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
            raise AssertionError(result.stderr)
        dry_status = json.loads((artifact / "status.json").read_text(encoding="utf-8"))
        assert dry_status["state"] == "dry_run"

        code, waiting = run_script(temp, validation_root)
        assert code == 0
        assert waiting["state"] == "waiting"

        code, blocked_wait = run_script(temp, validation_root, {"CRON_EVIDENCE_STRICT_WAIT": "true"})
        assert code == 2
        assert blocked_wait["state"] == "blocked"

        write_status(validation_root, "postgres-ops-20260620-080000", "passed")
        write_status(validation_root, "postgres-backup-retention-20260620-084500", "passed")
        code, passed = run_script(temp, validation_root)
        assert code == 0
        assert passed["state"] == "passed"

        write_status(validation_root, "postgres-ops-20260620-090000", "blocked")
        code, blocked = run_script(temp, validation_root)
        assert code == 2
        assert blocked["state"] == "blocked"

    print("postgres operational cron evidence verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
