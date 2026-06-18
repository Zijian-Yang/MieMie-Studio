#!/usr/bin/env python3
"""Verify the final JSON exit policy rollback script contract."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_rollback_final_json_exit_policy.sh"


def verify_dry_run_contract() -> None:
    if not SCRIPT.exists():
        raise AssertionError(f"missing rollback script: {SCRIPT.relative_to(ROOT_DIR)}")

    with tempfile.TemporaryDirectory(prefix="miemie-final-policy-rollback-") as temp_dir:
        root = Path(temp_dir)
        env_file = root / "compose.env"
        backup_file = root / "compose.env.before-final-json-exit.bak"
        env_file.write_text(
            "\n".join(
                [
                    "MIEMIE_DATABASE_ENABLED=true",
                    "MIEMIE_DATABASE_WRITE_MODE=postgres",
                    "MIEMIE_DATABASE_READ_MODE=postgres",
                    "MIEMIE_DATABASE_JSON_FALLBACK_READ=false",
                    "MIEMIE_POSTGRES_PASSWORD=active-secret-placeholder",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        backup_file.write_text(
            "\n".join(
                [
                    "MIEMIE_DATABASE_ENABLED=true",
                    "MIEMIE_DATABASE_WRITE_MODE=file",
                    "MIEMIE_DATABASE_READ_MODE=file",
                    "MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=video_studio_tasks",
                    "MIEMIE_DATABASE_JSON_FALLBACK_READ=true",
                    "MIEMIE_POSTGRES_PASSWORD=rollback-secret-placeholder",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        artifact_dir = root / "artifact"
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT_DIR,
            env={
                **os.environ,
                "RUN_ID": "verify-final-policy-rollback",
                "ARTIFACT_DIR": str(artifact_dir),
                "TMP_DIR": str(root / "tmp"),
                "ENV_FILE": str(env_file),
                "ROLLBACK_ENV_BACKUP_FILE": str(backup_file),
            },
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"dry-run failed with {result.returncode}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )

        status = json.loads((artifact_dir / "status.json").read_text(encoding="utf-8"))
        plan = (artifact_dir / "rollback-final-json-exit-policy-plan.sh").read_text(encoding="utf-8")
        current = env_file.read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert status["confirm"] == "dry-run"
        assert status["rollback_env_backup_file"] == str(backup_file)
        assert "MIEMIE_DATABASE_WRITE_MODE=postgres" in current

        for fragment in [
            "cp \"$ENV_FILE\" \"$PRE_ROLLBACK_BACKUP_FILE\"",
            "cp \"$ROLLBACK_ENV_BACKUP_FILE\" \"$ENV_FILE\"",
            "docker compose",
            "up -d api worker worker-video",
            "/api/health",
            "wait_for_health",
            "compose.env.rollback-source.sanitized",
            "compose.env.before-rollback.sanitized",
            "compose.env.after-rollback.sanitized",
        ]:
            assert fragment in plan, fragment


def verify_static_contract() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    for fragment in [
        "CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY",
        "ROLLBACK_ENV_BACKUP_FILE",
        "PRE_ROLLBACK_BACKUP_FILE",
        "write_status \"passed\" \"done\"",
        "redact_env_file",
        "health_check",
        "wait_for_health",
        "health check did not pass",
    ]:
        assert fragment in script, fragment


def main() -> int:
    verify_dry_run_contract()
    verify_static_contract()
    print("postgres rollback final JSON exit policy verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
