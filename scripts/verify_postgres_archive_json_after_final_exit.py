#!/usr/bin/env python3
"""Verify the post-final-exit JSON archive gate."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_archive_json_after_final_exit.py"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_completion_status(path: Path, state: str) -> None:
    write_json(
        path,
        {
            "run_id": "synthetic-completion",
            "state": state,
            "next_recommended_step": "archive_json_and_monitor_postgres_runtime",
        },
    )


def write_sample_data(data_root: Path) -> dict[str, Path]:
    files = {
        "session": data_root / "sessions.json",
        "root_config": data_root / "config.json",
        "users": data_root / "users.json",
        "project": data_root / "users/u1/projects/p1.json",
        "video_task": data_root / "users/u1/video_studio/t1.json",
        "studio_task": data_root / "users/u1/studio/i1.json",
        "user_config": data_root / "users/u1/config.json",
        "gallery": data_root / "users/u1/gallery/g1.json",
        "character": data_root / "users/u1/characters/c1.json",
        "benchmark": data_root / "users/u1/image_benchmark_runs/r1.json",
        "audio_task": data_root / "users/u1/audio_studio/a1.json",
        "voice": data_root / "users/u1/voices/v1.json",
    }
    for key, path in files.items():
        write_json(path, {"id": key, "value": "sample"})
    return files


def run_archive(*args: str, artifact_dir: Path) -> dict:
    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--artifact-dir",
            str(artifact_dir),
            "--run-id",
            "verify-json-archive",
            *args,
        ],
        cwd=ROOT_DIR,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"archive script failed with {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    status_path = artifact_dir / "status.json"
    summary_path = artifact_dir / "json-archive.summary.json"
    manifest_path = artifact_dir / "tracked-json-manifest.tsv"
    assert status_path.exists(), "missing status.json"
    return {
        "status": json.loads(status_path.read_text(encoding="utf-8")),
        "summary": json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {},
        "manifest": manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else "",
    }


def verify_non_complete_status_blocks_archival() -> None:
    if not SCRIPT.exists():
        raise AssertionError(f"missing JSON archive script: {SCRIPT.relative_to(ROOT_DIR)}")
    with tempfile.TemporaryDirectory(prefix="miemie-json-archive-blocked-") as temp_dir:
        root = Path(temp_dir)
        data_root = root / "data"
        files = write_sample_data(data_root)
        completion_status = root / "completion/status.json"
        write_completion_status(completion_status, "needs_final_exit_evidence")

        result = run_archive(
            "--data-root",
            str(data_root),
            "--completion-status",
            str(completion_status),
            artifact_dir=root / "artifact",
        )

        assert result["status"]["state"] == "blocked"
        assert result["status"]["stage"] == "completion-audit"
        assert files["project"].exists(), "blocked run must not move JSON files"
        assert files["root_config"].exists(), "blocked run must not touch root config"


def verify_dry_run_lists_only_tracked_business_json() -> None:
    with tempfile.TemporaryDirectory(prefix="miemie-json-archive-dry-run-") as temp_dir:
        root = Path(temp_dir)
        data_root = root / "data"
        write_sample_data(data_root)
        completion_status = root / "completion/status.json"
        write_completion_status(completion_status, "postgres_only_complete")

        result = run_archive(
            "--data-root",
            str(data_root),
            "--completion-status",
            str(completion_status),
            artifact_dir=root / "artifact",
        )

        assert result["status"]["state"] == "dry_run"
        assert result["summary"]["tracked_json_count"] == 10
        assert "users/u1/projects/p1.json" in result["manifest"]
        assert "users/u1/config.json" in result["manifest"]
        assert "sessions.json" in result["manifest"]
        manifest_paths = {
            line.split("\t")[1]
            for line in result["manifest"].splitlines()[1:]
            if line.strip()
        }
        assert "config.json" not in manifest_paths
        assert "users.json" not in manifest_paths


def verify_confirmed_archive_moves_tracked_files_and_keeps_sensitive_roots() -> None:
    with tempfile.TemporaryDirectory(prefix="miemie-json-archive-confirmed-") as temp_dir:
        root = Path(temp_dir)
        data_root = root / "data"
        files = write_sample_data(data_root)
        completion_status = root / "completion/status.json"
        write_completion_status(completion_status, "postgres_only_complete")
        quarantine_root = root / "quarantine"

        result = run_archive(
            "--data-root",
            str(data_root),
            "--completion-status",
            str(completion_status),
            "--quarantine-root",
            str(quarantine_root),
            "--confirm",
            "archive",
            artifact_dir=root / "artifact",
        )

        assert result["status"]["state"] == "passed"
        assert result["summary"]["tracked_json_count"] == 10
        assert result["summary"]["moved_count"] == 10
        assert Path(result["summary"]["tarball"]).exists()
        assert not files["project"].exists()
        assert not files["session"].exists()
        assert files["root_config"].exists()
        assert files["users"].exists()
        assert (quarantine_root / "users/u1/projects/p1.json").exists()
        assert (quarantine_root / "sessions.json").exists()


def main() -> int:
    verify_non_complete_status_blocks_archival()
    verify_dry_run_lists_only_tracked_business_json()
    verify_confirmed_archive_moves_tracked_files_and_keeps_sensitive_roots()
    print("postgres archive JSON after final exit verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
