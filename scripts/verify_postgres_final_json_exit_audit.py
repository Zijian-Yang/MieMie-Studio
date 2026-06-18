#!/usr/bin/env python3
"""Verify the final JSON exit audit contract."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_final_json_exit_audit.py"

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

EXPECTED_SEQUENCE = [
    "audit",
    "roll-runtime",
    "live-data-gate",
    "all-domain-dual-write-canary",
    "all-domain-read-switch-canary",
    "all-domain-rollback-read-switch",
    "all-domain-primary-write-canary",
    "all-domain-rollback-primary-write",
]


def run_audit(*args: str, artifact_dir: Path) -> dict:
    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--artifact-dir",
            str(artifact_dir),
            "--run-id",
            "verify-final-json-exit",
            *args,
        ],
        cwd=ROOT_DIR,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"final JSON exit audit failed with {result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    summary_path = artifact_dir / "final-json-exit-audit.summary.json"
    report_path = artifact_dir / "final-json-exit-audit.md"
    status_path = artifact_dir / "status.json"
    assert summary_path.exists(), "missing final-json-exit-audit.summary.json"
    assert report_path.exists(), "missing final-json-exit-audit.md"
    assert status_path.exists(), "missing status.json"
    return {
        "summary": json.loads(summary_path.read_text(encoding="utf-8")),
        "status": json.loads(status_path.read_text(encoding="utf-8")),
        "report": report_path.read_text(encoding="utf-8"),
    }


def write_sequence_artifact(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "status.json").write_text(
        json.dumps(
            {
                "run_id": "synthetic-server-sequence",
                "state": "passed",
                "stage": "done",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    rows = ["index\tmode\texit_code\tstate\tartifact_dir"]
    rows.extend(
        f"{index}\t{mode}\t0\tpassed\t/tmp/{mode}"
        for index, mode in enumerate(EXPECTED_SEQUENCE, start=1)
    )
    (path / "results.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")


def write_final_env(path: Path, *, fallback: bool = False) -> None:
    path.write_text(
        "\n".join(
            [
                "MIEMIE_DATABASE_ENABLED=true",
                "MIEMIE_DATABASE_WRITE_MODE=postgres",
                "MIEMIE_DATABASE_READ_MODE=postgres",
                "MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=",
                "MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=",
                "MIEMIE_DATABASE_READ_DOMAINS=",
                f"MIEMIE_DATABASE_JSON_FALLBACK_READ={'true' if fallback else 'false'}",
                "MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false",
                "MIEMIE_DATABASE_RECONCILE_STRICT=true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def verify_missing_evidence_is_not_ready() -> None:
    if not SCRIPT.exists():
        raise AssertionError(f"missing final JSON exit audit: {SCRIPT.relative_to(ROOT_DIR)}")

    with tempfile.TemporaryDirectory(prefix="miemie-final-json-exit-missing-") as temp_dir:
        result = run_audit(artifact_dir=Path(temp_dir) / "artifact")
        status = result["status"]
        summary = result["summary"]
        report = result["report"]

        assert status["state"] == "needs_server_sequence_evidence"
        assert status["next_recommended_step"] == "run_server_final_cutover_sequence"
        assert set(summary["expected_domains"]) == EXPECTED_DOMAINS
        assert "server_sequence_evidence" in {check["name"] for check in summary["checks"]}
        assert "`needs_server_sequence_evidence`" in report
        assert "MIEMIE_DATABASE_WRITE_MODE=postgres" in report
        assert "MIEMIE_DATABASE_JSON_FALLBACK_READ=false" in report


def verify_ready_env_requires_json_fallback_off() -> None:
    with tempfile.TemporaryDirectory(prefix="miemie-final-json-exit-ready-") as temp_dir:
        root = Path(temp_dir)
        sequence_dir = root / "sequence"
        env_file = root / "compose.env"
        write_sequence_artifact(sequence_dir)
        write_final_env(env_file)

        result = run_audit(
            "--sequence-artifact-dir",
            str(sequence_dir),
            "--env-file",
            str(env_file),
            artifact_dir=root / "artifact",
        )
        status = result["status"]
        summary = result["summary"]
        report = result["report"]

        assert status["state"] == "ready_for_post_json_exit_validation"
        assert status["next_recommended_step"] == "run_post_json_exit_health_reconcile_and_load_gates"
        checks = {check["name"]: check for check in summary["checks"]}
        assert checks["final_runtime_policy"]["state"] == "passed"
        assert checks["server_sequence_evidence"]["state"] == "passed"
        assert "`ready_for_post_json_exit_validation`" in report

        write_final_env(env_file, fallback=True)
        fallback_result = run_audit(
            "--sequence-artifact-dir",
            str(sequence_dir),
            "--env-file",
            str(env_file),
            artifact_dir=root / "artifact-fallback-on",
        )
        fallback_status = fallback_result["status"]
        fallback_summary = fallback_result["summary"]
        assert fallback_status["state"] == "needs_final_runtime_policy"
        assert fallback_summary["checks_by_name"]["final_runtime_policy"]["state"] == "needs_work"


def main() -> int:
    verify_missing_evidence_is_not_ready()
    verify_ready_env_requires_json_fallback_off()
    print("postgres final JSON exit audit verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
