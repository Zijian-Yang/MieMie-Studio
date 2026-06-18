#!/usr/bin/env python3
"""Verify the final PostgreSQL-only completion audit contract."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_final_exit_completion_audit.py"


def run_audit(*args: str, artifact_dir: Path) -> dict:
    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--artifact-dir",
            str(artifact_dir),
            "--run-id",
            "verify-final-exit-completion",
            *args,
        ],
        cwd=ROOT_DIR,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"final exit completion audit failed with {result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    summary_path = artifact_dir / "final-exit-completion.summary.json"
    report_path = artifact_dir / "final-exit-completion.md"
    status_path = artifact_dir / "status.json"
    assert summary_path.exists(), "missing final-exit-completion.summary.json"
    assert report_path.exists(), "missing final-exit-completion.md"
    assert status_path.exists(), "missing status.json"
    return {
        "summary": json.loads(summary_path.read_text(encoding="utf-8")),
        "status": json.loads(status_path.read_text(encoding="utf-8")),
        "report": report_path.read_text(encoding="utf-8"),
    }


def write_status(path: Path, state: str, *, stage: str = "done", reason: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_id": path.parent.name,
                "state": state,
                "stage": stage,
                "reason": reason,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_final_exit_artifact(root: Path, *, rollback_state: str | None = None) -> None:
    write_status(root / "status.json", "passed")
    write_status(root / "server-sequence" / "status.json", "passed")
    write_status(root / "server-sequence" / "sequence" / "status.json", "passed")
    write_status(root / "apply-final-json-exit-policy" / "status.json", "passed")
    write_status(root / "apply-final-json-exit-policy" / "final-json-exit-audit" / "status.json", "ready_for_post_json_exit_validation")
    write_status(root / "post-json-exit-validation" / "status.json", "passed")
    write_status(root / "post-json-exit-validation" / "final-json-exit-audit" / "status.json", "ready_for_post_json_exit_validation")
    if rollback_state is not None:
        write_status(root / "rollback-final-json-exit-policy" / "status.json", rollback_state)


def verify_missing_evidence_is_not_complete() -> None:
    if not SCRIPT.exists():
        raise AssertionError(f"missing final exit completion audit: {SCRIPT.relative_to(ROOT_DIR)}")

    with tempfile.TemporaryDirectory(prefix="miemie-final-exit-missing-") as temp_dir:
        result = run_audit(artifact_dir=Path(temp_dir) / "artifact")
        status = result["status"]
        summary = result["summary"]
        report = result["report"]

        assert status["state"] == "needs_final_exit_evidence"
        assert status["next_recommended_step"] == "run_server_final_exit_sequence"
        assert summary["checks_by_name"]["server_final_exit_status"]["state"] == "needs_work"
        assert "`needs_final_exit_evidence`" in report


def verify_complete_artifact_passes_and_rollback_blocks_completion() -> None:
    with tempfile.TemporaryDirectory(prefix="miemie-final-exit-complete-") as temp_dir:
        root = Path(temp_dir)
        final_exit_dir = root / "server-final-exit"
        write_final_exit_artifact(final_exit_dir)

        result = run_audit(
            "--final-exit-artifact-dir",
            str(final_exit_dir),
            artifact_dir=root / "artifact",
        )
        status = result["status"]
        summary = result["summary"]
        report = result["report"]

        assert status["state"] == "postgres_only_complete"
        assert status["next_recommended_step"] == "archive_json_and_monitor_postgres_runtime"
        assert summary["checks_by_name"]["post_json_exit_validation"]["state"] == "passed"
        assert summary["checks_by_name"]["rollback_not_triggered"]["state"] == "passed"
        assert "`postgres_only_complete`" in report

        rollback_dir = root / "server-final-exit-rollback"
        write_final_exit_artifact(rollback_dir, rollback_state="passed")
        rollback_result = run_audit(
            "--final-exit-artifact-dir",
            str(rollback_dir),
            artifact_dir=root / "artifact-rollback",
        )
        rollback_status = rollback_result["status"]
        rollback_summary = rollback_result["summary"]
        assert rollback_status["state"] == "rolled_back_after_final_exit_attempt"
        assert rollback_status["next_recommended_step"] == "diagnose_final_exit_failure_before_retry"
        assert rollback_summary["checks_by_name"]["rollback_not_triggered"]["state"] == "failed"


def main() -> int:
    verify_missing_evidence_is_not_complete()
    verify_complete_artifact_passes_and_rollback_blocks_completion()
    print("postgres final exit completion audit verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
