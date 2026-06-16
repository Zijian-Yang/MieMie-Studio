#!/usr/bin/env python3
"""Verify the PostgreSQL domain coverage audit report contract."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_domain_coverage.py"

EXPECTED_MIGRATED_DOMAINS = {
    "video_studio_tasks",
    "studio_tasks",
    "projects",
    "media_metadata",
    "project_entities",
    "benchmark_records",
    "user_config",
    "sessions",
}

AUDIO_EXPECTED_MISSING = {
    "backend/app/repositories/audio_studio_runtime.py",
    "backend/app/services/migration/backfill_audio_studio.py",
    "backend/app/services/migration/reconcile_audio_studio.py",
    "scripts/postgres_backfill_audio_studio.py",
    "scripts/postgres_reconcile_audio_studio.py",
}

AUDIO_EXPECTED_PRESENT = {
    "backend/app/db/schema/audio_studio.py",
    "backend/app/repositories/audio_studio.py",
}

AUDIO_STORAGE_METHODS = {
    "save_audio_studio_task",
    "get_audio_studio_task",
    "get_audio_studio_tasks",
    "delete_audio_studio_task",
    "save_voice_profile",
    "get_voice_profile",
    "get_voice_profiles",
    "get_voice_profile_by_voice_id",
    "delete_voice_profile",
}


def run_report_contract() -> None:
    if not SCRIPT.exists():
        raise AssertionError(f"missing coverage script: {SCRIPT.relative_to(ROOT_DIR)}")

    with tempfile.TemporaryDirectory(prefix="miemie-domain-coverage-") as temp_dir:
        artifact_dir = Path(temp_dir) / "artifact"
        result = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--artifact-dir",
                str(artifact_dir),
                "--run-id",
                "verify-domain-coverage",
            ],
            cwd=ROOT_DIR,
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"coverage report failed with {result.returncode}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )

        summary_path = artifact_dir / "domain-coverage.summary.json"
        report_path = artifact_dir / "domain-coverage.md"
        status_path = artifact_dir / "status.json"
        assert summary_path.exists(), "missing domain-coverage.summary.json"
        assert report_path.exists(), "missing domain-coverage.md"
        assert status_path.exists(), "missing status.json"

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        status = json.loads(status_path.read_text(encoding="utf-8"))
        report = report_path.read_text(encoding="utf-8")

        assert status["state"] == "ready_for_next_domain"
        assert status["next_recommended_domain"] == "audio_studio"
        assert status["pending_domain_count"] == 1
        assert status["migrated_domain_count"] == len(EXPECTED_MIGRATED_DOMAINS)

        migrated = {item["name"]: item for item in summary["migrated_domains"]}
        assert set(migrated) == EXPECTED_MIGRATED_DOMAINS
        for name, item in migrated.items():
            assert item["status"] == "covered", name
            assert item["missing_files"] == [], name

        pending = {item["name"]: item for item in summary["pending_domains"]}
        assert set(pending) == {"audio_studio"}
        audio = pending["audio_studio"]
        assert audio["status"] == "in_progress"
        assert set(audio["missing_expected_files"]) == AUDIO_EXPECTED_MISSING
        assert AUDIO_EXPECTED_PRESENT.issubset(set(audio["present_expected_files"]))
        assert AUDIO_STORAGE_METHODS.issubset(set(audio["storage_methods"]))
        assert "audio_studio/*.json" in audio["json_surfaces"]
        assert "voices/*.json" in audio["json_surfaces"]

        embedded = {item["surface"]: item for item in summary["covered_embedded_surfaces"]}
        assert embedded["scripts/shots"]["covered_by"] == "projects.raw_project_snapshot"

        assert "## Next Recommended Domain" in report
        assert "`audio_studio`" in report
        assert "`projects.raw_project_snapshot`" in report


def check_source_contract() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        "video_studio_tasks",
        "studio_tasks",
        "projects",
        "media_metadata",
        "project_entities",
        "benchmark_records",
        "user_config",
        "sessions",
        "audio_studio",
        "voices/*.json",
        "projects.raw_project_snapshot",
        "ready_for_next_domain",
    ]
    for fragment in required_fragments:
        if fragment not in content:
            raise AssertionError(f"missing source fragment: {fragment}")


def main() -> int:
    run_report_contract()
    check_source_contract()
    print("postgres domain coverage verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
