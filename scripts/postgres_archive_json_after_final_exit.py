#!/usr/bin/env python3
"""Archive tracked JSON business-state files after final PostgreSQL exit.

This command is intentionally gated. It refuses to move any JSON file unless a
final exit completion audit status reports `postgres_only_complete`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = (
    ROOT_DIR
    / "docs"
    / "reports"
    / "artifacts"
    / "2026-06-07-postgres-upgrade-rollout"
    / "r87-archive-json-after-final-exit"
)
DEFAULT_COMPLETION_STATUS = (
    ROOT_DIR
    / "docs"
    / "reports"
    / "artifacts"
    / "2026-06-07-postgres-upgrade-rollout"
    / "r86-final-exit-completion-audit"
    / "status.json"
)
DEFAULT_DATA_ROOT = ROOT_DIR / "backend" / "data"

USER_JSON_DIRECTORIES = (
    "projects",
    "video_studio",
    "studio",
    "gallery",
    "audio",
    "video_library",
    "text_library",
    "characters",
    "scenes",
    "props",
    "frames",
    "videos",
    "styles",
    "image_benchmark_datasets",
    "image_benchmark_suites",
    "image_benchmark_runs",
    "video_benchmark_datasets",
    "video_benchmark_suites",
    "video_benchmark_runs",
    "audio_studio",
    "voices",
)


@dataclass(frozen=True)
class TrackedJsonFile:
    domain: str
    path: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def discover_tracked_json_files(data_root: Path) -> list[TrackedJsonFile]:
    files: list[TrackedJsonFile] = []

    sessions_path = data_root / "sessions.json"
    if sessions_path.exists():
        files.append(TrackedJsonFile("sessions", sessions_path))

    users_dir = data_root / "users"
    if not users_dir.exists():
        return files

    for user_dir in sorted(path for path in users_dir.iterdir() if path.is_dir()):
        config_path = user_dir / "config.json"
        if config_path.exists():
            files.append(TrackedJsonFile("user_config", config_path))
        for directory in USER_JSON_DIRECTORIES:
            item_dir = user_dir / directory
            if not item_dir.exists():
                continue
            for item_path in sorted(item_dir.glob("*.json")):
                files.append(TrackedJsonFile(directory, item_path))
    return files


def relative_to_data_root(path: Path, data_root: Path) -> Path:
    return path.relative_to(data_root)


def write_manifest(files: Iterable[TrackedJsonFile], data_root: Path, artifact_dir: Path) -> Path:
    manifest = artifact_dir / "tracked-json-manifest.tsv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", encoding="utf-8") as handle:
        handle.write("domain\trelative_path\tbytes\n")
        for item in files:
            relative_path = relative_to_data_root(item.path, data_root)
            handle.write(f"{item.domain}\t{relative_path.as_posix()}\t{item.path.stat().st_size}\n")
    return manifest


def assert_completion_ready(completion_status: Path) -> tuple[bool, str, str]:
    if not completion_status.exists():
        return False, "missing completion status", ""
    status = read_json(completion_status)
    state = str(status.get("state", ""))
    if state != "postgres_only_complete":
        return False, f"completion status is {state}", state
    return True, "", state


def create_tarball(files: list[TrackedJsonFile], data_root: Path, artifact_dir: Path, run_id: str) -> Path:
    tarball = artifact_dir / f"tracked-json-before-archive.{run_id}.tar.gz"
    tarball.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball, "w:gz") as archive:
        for item in files:
            archive.add(item.path, arcname=relative_to_data_root(item.path, data_root).as_posix())
    return tarball


def move_to_quarantine(files: list[TrackedJsonFile], data_root: Path, quarantine_root: Path) -> int:
    moved_count = 0
    for item in files:
        relative_path = relative_to_data_root(item.path, data_root)
        target = quarantine_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(item.path), str(target))
        moved_count += 1
    return moved_count


def build_summary(
    *,
    run_id: str,
    state: str,
    stage: str,
    reason: str,
    data_root: Path,
    completion_status: Path,
    completion_state: str,
    artifact_dir: Path,
    manifest_path: Path | None,
    tracked_files: list[TrackedJsonFile],
    moved_count: int = 0,
    tarball: Path | None = None,
    quarantine_root: Path | None = None,
) -> dict:
    return {
        "run_id": run_id,
        "updated_at": utc_now(),
        "state": state,
        "stage": stage,
        "reason": reason,
        "data_root": rel(data_root),
        "completion_status": rel(completion_status),
        "completion_state": completion_state,
        "artifact_dir": rel(artifact_dir),
        "manifest": rel(manifest_path) if manifest_path else "",
        "tracked_json_count": len(tracked_files),
        "tracked_json_count_by_domain": count_by_domain(tracked_files),
        "moved_count": moved_count,
        "tarball": rel(tarball) if tarball else "",
        "quarantine_root": rel(quarantine_root) if quarantine_root else "",
        "notes": [
            "Root backend/data/config.json, users.json, and config.example.json are intentionally excluded.",
            "This gate only archives tracked business-state JSON that already has PostgreSQL migration coverage.",
            "Use --confirm archive only after final exit completion audit reports postgres_only_complete.",
        ],
    }


def count_by_domain(files: list[TrackedJsonFile]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in files:
        counts[item.domain] = counts.get(item.domain, 0) + 1
    return dict(sorted(counts.items()))


def write_outputs(summary: dict, artifact_dir: Path) -> None:
    write_json(artifact_dir / "json-archive.summary.json", summary)
    write_json(
        artifact_dir / "status.json",
        {
            "run_id": summary["run_id"],
            "state": summary["state"],
            "stage": summary["stage"],
            "reason": summary["reason"],
            "tracked_json_count": summary["tracked_json_count"],
            "moved_count": summary["moved_count"],
            "artifact_dir": summary["artifact_dir"],
            "updated_at": summary["updated_at"],
        },
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--completion-status", type=Path, default=DEFAULT_COMPLETION_STATUS)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--run-id", default="postgres-archive-json-after-final-exit")
    parser.add_argument("--confirm", default="dry-run", choices=["dry-run", "archive"])
    parser.add_argument("--quarantine-root", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact_dir = args.artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)

    completion_ok, reason, completion_state = assert_completion_ready(args.completion_status)
    if not completion_ok:
        summary = build_summary(
            run_id=args.run_id,
            state="blocked",
            stage="completion-audit",
            reason=reason,
            data_root=args.data_root,
            completion_status=args.completion_status,
            completion_state=completion_state,
            artifact_dir=artifact_dir,
            manifest_path=None,
            tracked_files=[],
        )
        write_outputs(summary, artifact_dir)
        print(f"blocked: {reason}")
        return 0

    tracked_files = discover_tracked_json_files(args.data_root)
    manifest_path = write_manifest(tracked_files, args.data_root, artifact_dir)

    if args.confirm != "archive":
        summary = build_summary(
            run_id=args.run_id,
            state="dry_run",
            stage="planned",
            reason="set --confirm archive to archive tracked JSON files",
            data_root=args.data_root,
            completion_status=args.completion_status,
            completion_state=completion_state,
            artifact_dir=artifact_dir,
            manifest_path=manifest_path,
            tracked_files=tracked_files,
        )
        write_outputs(summary, artifact_dir)
        print(f"dry-run tracked JSON manifest written to {rel(manifest_path)}")
        return 0

    quarantine_root = args.quarantine_root or (args.data_root / "_postgres_final_json_archive" / args.run_id)
    tarball = create_tarball(tracked_files, args.data_root, artifact_dir, args.run_id)
    moved_count = move_to_quarantine(tracked_files, args.data_root, quarantine_root)
    summary = build_summary(
        run_id=args.run_id,
        state="passed",
        stage="done",
        reason="tracked JSON files archived and quarantined",
        data_root=args.data_root,
        completion_status=args.completion_status,
        completion_state=completion_state,
        artifact_dir=artifact_dir,
        manifest_path=manifest_path,
        tracked_files=tracked_files,
        moved_count=moved_count,
        tarball=tarball,
        quarantine_root=quarantine_root,
    )
    write_outputs(summary, artifact_dir)
    print(f"archived {moved_count} tracked JSON files")
    print(f"tarball: {rel(tarball)}")
    print(f"quarantine root: {rel(quarantine_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
