#!/usr/bin/env python3
"""Verify the post-JSON-exit validation script contract."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_post_json_exit_validation.sh"

EXPECTED_DOMAINS = [
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


def verify_dry_run_contract() -> None:
    if not SCRIPT.exists():
        raise AssertionError(f"missing post JSON exit validation script: {SCRIPT.relative_to(ROOT_DIR)}")

    with tempfile.TemporaryDirectory(prefix="miemie-post-json-exit-") as temp_dir:
        artifact_dir = Path(temp_dir) / "artifact"
        result = subprocess.run(
            [
                "bash",
                str(SCRIPT),
            ],
            cwd=ROOT_DIR,
            env={
                **dict(),
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin",
                "RUN_ID": "verify-post-json-exit-validation",
                "ARTIFACT_DIR": str(artifact_dir),
                "TMP_DIR": str(Path(temp_dir) / "tmp"),
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

        status_path = artifact_dir / "status.json"
        plan_path = artifact_dir / "post-json-exit-validation-plan.sh"
        domains_path = artifact_dir / "domains.txt"
        assert status_path.exists(), "missing status.json"
        assert plan_path.exists(), "missing post-json-exit-validation-plan.sh"
        assert domains_path.exists(), "missing domains.txt"

        status = json.loads(status_path.read_text(encoding="utf-8"))
        plan = plan_path.read_text(encoding="utf-8")
        domains = domains_path.read_text(encoding="utf-8").splitlines()

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert status["confirm"] == "dry-run"
        assert status["run_load_gate"] == "true"
        assert domains == EXPECTED_DOMAINS

        required_fragments = [
            "postgres_final_json_exit_audit.py",
            "ready_for_post_json_exit_validation",
            "MIEMIE_DATABASE_WRITE_MODE=postgres",
            "MIEMIE_DATABASE_READ_MODE=postgres",
            "MIEMIE_DATABASE_JSON_FALLBACK_READ=false",
            "MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false",
            "/api/health",
            "docker compose",
            "docker stats --no-stream",
            "k6 run loadtest/k6/s1-read.js",
            "K6_VUS=30",
            "K6_DURATION=90s",
        ]
        for fragment in required_fragments:
            assert fragment in plan, fragment

        for domain in EXPECTED_DOMAINS:
            assert f"postgres_reconcile_{domain}.py" in plan


def verify_script_static_contract() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    for fragment in [
        "CONFIRM_POST_JSON_EXIT_VALIDATION",
        "POST_JSON_EXIT_RUN_LOAD_GATE",
        "SEQUENCE_ARTIFACT_DIR",
        "scripts/postgres_final_json_exit_audit.py",
        "ready_for_post_json_exit_validation",
        "write_status \"blocked\"",
        "write_status \"passed\" \"done\"",
    ]:
        assert fragment in script, fragment


def main() -> int:
    verify_dry_run_contract()
    verify_script_static_contract()
    print("postgres post JSON exit validation verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
