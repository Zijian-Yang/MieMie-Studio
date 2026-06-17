"""Backfill audio studio JSON files into PostgreSQL repositories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from app.models.audio_studio import AudioStudioTask, VoiceProfile
from app.repositories.base import AudioStudioRepository


RepositoryFactory = Callable[[str], AudioStudioRepository]


@dataclass(frozen=True)
class AudioStudioJsonTaskRecord:
    user_id: str
    task: AudioStudioTask
    source_path: Path


@dataclass(frozen=True)
class VoiceProfileJsonRecord:
    user_id: str
    profile: VoiceProfile
    source_path: Path


def iter_audio_studio_json_tasks(
    data_root: str | Path,
    *,
    on_error: Optional[Callable[[str, Path, Exception], None]] = None,
) -> Iterable[AudioStudioJsonTaskRecord]:
    """Yield valid per-user audio studio tasks from `data/users/*/audio_studio`."""

    users_dir = Path(data_root) / "users"
    if not users_dir.exists():
        return

    for user_dir in sorted(path for path in users_dir.iterdir() if path.is_dir()):
        task_dir = user_dir / "audio_studio"
        if not task_dir.exists():
            continue
        for task_path in sorted(task_dir.glob("*.json")):
            try:
                with task_path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                yield AudioStudioJsonTaskRecord(
                    user_id=user_dir.name,
                    task=AudioStudioTask(**data),
                    source_path=task_path,
                )
            except Exception as exc:
                if on_error:
                    on_error(user_dir.name, task_path, exc)


def iter_voice_profile_json_records(
    data_root: str | Path,
    *,
    on_error: Optional[Callable[[str, Path, Exception], None]] = None,
) -> Iterable[VoiceProfileJsonRecord]:
    """Yield valid per-user voice profiles from `data/users/*/voices`."""

    users_dir = Path(data_root) / "users"
    if not users_dir.exists():
        return

    for user_dir in sorted(path for path in users_dir.iterdir() if path.is_dir()):
        voices_dir = user_dir / "voices"
        if not voices_dir.exists():
            continue
        for profile_path in sorted(voices_dir.glob("*.json")):
            try:
                with profile_path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                yield VoiceProfileJsonRecord(
                    user_id=user_dir.name,
                    profile=VoiceProfile(**data),
                    source_path=profile_path,
                )
            except Exception as exc:
                if on_error:
                    on_error(user_dir.name, profile_path, exc)


def _failure(user_id: str, kind: str, source_path: Path, exc: Exception) -> dict:
    return {
        "user_id": user_id,
        "kind": kind,
        "file": source_path.name,
        "error": exc.__class__.__name__,
    }


def backfill_audio_studio(
    data_root: str | Path,
    repository_factory: RepositoryFactory,
) -> dict:
    """Upsert valid audio studio tasks and voice profiles into PostgreSQL."""

    failures: list[dict] = []
    scanned_users: set[str] = set()
    json_task_count = 0
    json_voice_profile_count = 0
    tasks_upserted_count = 0
    voice_profiles_upserted_count = 0

    def record_task_load_failure(user_id: str, source_path: Path, exc: Exception) -> None:
        failures.append(_failure(user_id, "audio_studio_task", source_path, exc))

    def record_profile_load_failure(user_id: str, source_path: Path, exc: Exception) -> None:
        failures.append(_failure(user_id, "voice_profile", source_path, exc))

    for record in iter_audio_studio_json_tasks(data_root, on_error=record_task_load_failure):
        scanned_users.add(record.user_id)
        json_task_count += 1
        try:
            repository_factory(record.user_id).save_task(record.task)
            tasks_upserted_count += 1
        except Exception as exc:
            failures.append(_failure(record.user_id, "audio_studio_task", record.source_path, exc))

    for record in iter_voice_profile_json_records(
        data_root,
        on_error=record_profile_load_failure,
    ):
        scanned_users.add(record.user_id)
        json_voice_profile_count += 1
        try:
            repository_factory(record.user_id).save_voice_profile(record.profile)
            voice_profiles_upserted_count += 1
        except Exception as exc:
            failures.append(_failure(record.user_id, "voice_profile", record.source_path, exc))

    return {
        "domain": "audio_studio",
        "scanned_users": sorted(scanned_users),
        "json_task_count": json_task_count,
        "json_voice_profile_count": json_voice_profile_count,
        "tasks_upserted_count": tasks_upserted_count,
        "voice_profiles_upserted_count": voice_profiles_upserted_count,
        "failed_count": len(failures),
        "failures": failures,
        "ok": len(failures) == 0,
    }


def write_backfill_summary(summary: dict, output_path: str | Path) -> Path:
    """Write a sanitized audio studio backfill summary JSON file."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path
