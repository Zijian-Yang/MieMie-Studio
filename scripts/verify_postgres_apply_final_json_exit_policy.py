#!/usr/bin/env python3
"""Verify the final PostgreSQL-only policy application script contract."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_apply_final_json_exit_policy.sh"

REQUIRED_ASSIGNMENTS = [
    "MIEMIE_DATABASE_ENABLED=true",
    "MIEMIE_DATABASE_WRITE_MODE=postgres",
    "MIEMIE_DATABASE_READ_MODE=postgres",
    "MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=",
    "MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=",
    "MIEMIE_DATABASE_READ_DOMAINS=",
    "MIEMIE_DATABASE_JSON_FALLBACK_READ=false",
    "MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false",
    "MIEMIE_DATABASE_RECONCILE_STRICT=true",
]


def verify_dry_run_contract() -> None:
    if not SCRIPT.exists():
        raise AssertionError(f"missing final policy script: {SCRIPT.relative_to(ROOT_DIR)}")

    with tempfile.TemporaryDirectory(prefix="miemie-final-policy-") as temp_dir:
        root = Path(temp_dir)
        env_file = root / "compose.env"
        env_file.write_text(
            "\n".join(
                [
                    "MIEMIE_DATABASE_ENABLED=false",
                    "MIEMIE_DATABASE_WRITE_MODE=file",
                    "MIEMIE_DATABASE_READ_MODE=file",
                    "MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=video_studio_tasks",
                    "MIEMIE_DATABASE_JSON_FALLBACK_READ=true",
                    "MIEMIE_POSTGRES_PASSWORD=super-secret-placeholder",
                    "MIEMIE_DATABASE_URL=postgresql+psycopg://miemie:${MIEMIE_POSTGRES_PASSWORD}@postgres:5432/miemie",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        sequence_dir = root / "sequence"
        sequence_dir.mkdir()
        (sequence_dir / "status.json").write_text('{"state":"passed"}\n', encoding="utf-8")
        (sequence_dir / "results.tsv").write_text("index\tmode\texit_code\tstate\tartifact_dir\n", encoding="utf-8")

        artifact_dir = root / "artifact"
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT_DIR,
            env={
                **os.environ,
                "RUN_ID": "verify-final-policy",
                "ARTIFACT_DIR": str(artifact_dir),
                "TMP_DIR": str(root / "tmp"),
                "ENV_FILE": str(env_file),
                "SEQUENCE_ARTIFACT_DIR": str(sequence_dir),
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
        plan = (artifact_dir / "apply-final-json-exit-policy-plan.sh").read_text(encoding="utf-8")
        sanitized = (artifact_dir / "compose.env.final-policy.sanitized").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert status["confirm"] == "dry-run"
        assert status["sequence_artifact_dir"] == str(sequence_dir)
        assert env_file.read_text(encoding="utf-8").splitlines()[0] == "MIEMIE_DATABASE_ENABLED=false"

        for assignment in REQUIRED_ASSIGNMENTS:
            assert assignment in plan, assignment
            assert assignment in sanitized, assignment

        assert "cp \"$ENV_FILE\" \"$BACKUP_FILE\"" in plan
        assert "postgres_final_json_exit_audit.py" in plan
        assert "ready_for_post_json_exit_validation" in plan
        assert "super-secret-placeholder" not in sanitized
        assert "<redacted>" in sanitized


def verify_script_static_contract() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    for fragment in [
        "CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY",
        "SEQUENCE_ARTIFACT_DIR",
        "set_env_value MIEMIE_DATABASE_WRITE_MODE postgres",
        "set_env_value MIEMIE_DATABASE_JSON_FALLBACK_READ false",
        "set_env_value MIEMIE_DATABASE_JSON_ARCHIVE_WRITES false",
        "postgres_final_json_exit_audit.py",
        "ready_for_post_json_exit_validation",
        "write_status \"passed\" \"done\"",
    ]:
        assert fragment in script, fragment


def main() -> int:
    verify_dry_run_contract()
    verify_script_static_contract()
    print("postgres apply final JSON exit policy verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
