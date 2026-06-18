#!/usr/bin/env python3
"""Verify the final PostgreSQL cutover readiness audit contract."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_final_cutover_readiness.py"

EXPECTED_DOMAINS = {
    "video_studio_tasks",
    "studio_tasks",
    "projects",
    "media_metadata",
    "project_entities",
    "benchmark_records",
    "user_config",
    "sessions",
    "audio_studio",
}


def run_readiness_contract() -> None:
    if not SCRIPT.exists():
        raise AssertionError(f"missing readiness script: {SCRIPT.relative_to(ROOT_DIR)}")

    with tempfile.TemporaryDirectory(prefix="miemie-final-cutover-") as temp_dir:
        artifact_dir = Path(temp_dir) / "artifact"
        result = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--artifact-dir",
                str(artifact_dir),
                "--run-id",
                "verify-final-cutover-readiness",
            ],
            cwd=ROOT_DIR,
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"readiness report failed with {result.returncode}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )

        summary_path = artifact_dir / "final-cutover-readiness.summary.json"
        report_path = artifact_dir / "final-cutover-readiness.md"
        status_path = artifact_dir / "status.json"
        assert summary_path.exists(), "missing final-cutover-readiness.summary.json"
        assert report_path.exists(), "missing final-cutover-readiness.md"
        assert status_path.exists(), "missing status.json"

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        status = json.loads(status_path.read_text(encoding="utf-8"))
        report = report_path.read_text(encoding="utf-8")

        assert status["state"] == "ready_for_final_cutover_sequence"
        assert status["next_recommended_step"] == "run_server_final_cutover_sequence"
        assert set(summary["expected_domains"]) == EXPECTED_DOMAINS

        checks = {item["name"]: item for item in summary["checks"]}
        assert checks["domain_coverage"]["state"] == "passed"
        assert checks["live_data_gate_domains"]["state"] == "passed"
        assert checks["staging_sequence_order"]["state"] == "passed"
        assert checks["server_fallback_contract"]["state"] == "passed"

        app_canary = checks["app_canary_domain_coverage"]
        assert app_canary["state"] == "passed"
        assert set(app_canary["covered_domains"]) == EXPECTED_DOMAINS
        assert app_canary["missing_domains"] == []

        assert "# Final PostgreSQL Cutover Readiness Audit" in report
        assert "`ready_for_final_cutover_sequence`" in report
        assert "`run_server_final_cutover_sequence`" in report
        assert "`audio_studio`" in report


def main() -> int:
    run_readiness_contract()
    print("postgres final cutover readiness verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
