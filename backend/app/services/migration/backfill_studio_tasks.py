"""Backfill image studio task JSON files into PostgreSQL repositories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from app.models.studio import StudioTask
from app.repositories.base import StudioTaskRepository


RepositoryFactory = Callable[[str], StudioTaskRepository]


@dataclass(frozen=True)
class StudioJsonTaskRecord:
    user_id: str
    task: StudioTask
    source_path: Path


def iter_studio_json_tasks(
    data_root: str | Path,
    *,
    on_error: Optional[Callable[[str, Path, Exception], None]] = None,
) -> Iterable[StudioJsonTaskRecord]:
    """Yield valid per-user image studio tasks from `data/users/*/studio`."""

    users_dir = Path(data_root) / "users"
    if not users_dir.exists():
        return

    for user_dir in sorted(path for path in users_dir.iterdir() if path.is_dir()):
        task_dir = user_dir / "studio"
        if not task_dir.exists():
            continue
        for task_path in sorted(task_dir.glob("*.json")):
            try:
                with task_path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                yield StudioJsonTaskRecord(
                    user_id=user_dir.name,
                    task=StudioTask(**data),
                    source_path=task_path,
                )
            except Exception as exc:
                if on_error:
                    on_error(user_dir.name, task_path, exc)


def backfill_studio_tasks(
    data_root: str | Path,
    repository_factory: RepositoryFactory,
) -> dict:
    """Upsert all valid per-user JSON image studio tasks into PostgreSQL."""

    failures: list[dict] = []
    scanned_users: set[str] = set()
    json_count = 0
    upserted_count = 0

    def record_load_failure(user_id: str, task_path: Path, exc: Exception) -> None:
        failures.append(
            {
                "user_id": user_id,
                "task_file": task_path.name,
                "error": exc.__class__.__name__,
            }
        )

    for record in iter_studio_json_tasks(data_root, on_error=record_load_failure):
        scanned_users.add(record.user_id)
        json_count += 1
        try:
            repository_factory(record.user_id).save(record.task)
            upserted_count += 1
        except Exception as exc:
            failures.append(
                {
                    "user_id": record.user_id,
                    "task_id": record.task.id,
                    "error": exc.__class__.__name__,
                }
            )

    return {
        "domain": "studio_tasks",
        "scanned_users": sorted(scanned_users),
        "json_count": json_count,
        "upserted_count": upserted_count,
        "failed_count": len(failures),
        "failures": failures,
        "ok": len(failures) == 0,
    }


def write_backfill_summary(summary: dict, output_path: str | Path) -> Path:
    """Write a sanitized backfill summary JSON file."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path
