"""Reconcile JSON and PostgreSQL audio studio state."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.audio_studio import AudioStudioTask, VoiceProfile
from app.services.migration.backfill_audio_studio import (
    RepositoryFactory,
    iter_audio_studio_json_tasks,
    iter_voice_profile_json_records,
)


TASK_SAFE_COMPARE_FIELDS = ("project_id", "task_type", "status", "result_voice_id", "updated_at")
VOICE_PROFILE_SAFE_COMPARE_FIELDS = (
    "project_id",
    "voice_id",
    "source",
    "target_model",
    "status",
    "updated_at",
)


def _safe_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _safe_projection(item: AudioStudioTask | VoiceProfile, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: _safe_value(getattr(item, field, None)) for field in fields}


def _load_json_state(data_root: str | Path) -> tuple[dict[str, dict[str, AudioStudioTask]], dict[str, dict[str, VoiceProfile]], list[dict]]:
    json_tasks_by_user: dict[str, dict[str, AudioStudioTask]] = {}
    json_profiles_by_user: dict[str, dict[str, VoiceProfile]] = {}
    load_failures: list[dict] = []

    def record_task_load_failure(user_id: str, source_path: Path, exc: Exception) -> None:
        load_failures.append(
            {
                "user_id": user_id,
                "kind": "audio_studio_task",
                "file": source_path.name,
                "error": exc.__class__.__name__,
            }
        )

    def record_profile_load_failure(user_id: str, source_path: Path, exc: Exception) -> None:
        load_failures.append(
            {
                "user_id": user_id,
                "kind": "voice_profile",
                "file": source_path.name,
                "error": exc.__class__.__name__,
            }
        )

    for record in iter_audio_studio_json_tasks(data_root, on_error=record_task_load_failure):
        json_tasks_by_user.setdefault(record.user_id, {})[record.task.id] = record.task

    for record in iter_voice_profile_json_records(data_root, on_error=record_profile_load_failure):
        json_profiles_by_user.setdefault(record.user_id, {})[record.profile.id] = record.profile

    return json_tasks_by_user, json_profiles_by_user, load_failures


def _reconcile_collection(
    *,
    user_id: str,
    kind: str,
    json_items: dict[str, Any],
    postgres_items: dict[str, Any],
    compare_fields: tuple[str, ...],
    missing_in_postgres: list[dict],
    missing_in_json: list[dict],
    field_differences: list[dict],
) -> None:
    for item_id in sorted(set(json_items) - set(postgres_items)):
        missing_in_postgres.append({"user_id": user_id, "kind": kind, "id": item_id})

    for item_id in sorted(set(postgres_items) - set(json_items)):
        missing_in_json.append({"user_id": user_id, "kind": kind, "id": item_id})

    for item_id in sorted(set(json_items) & set(postgres_items)):
        json_projection = _safe_projection(json_items[item_id], compare_fields)
        postgres_projection = _safe_projection(postgres_items[item_id], compare_fields)
        for field in compare_fields:
            if json_projection[field] != postgres_projection[field]:
                field_differences.append(
                    {
                        "user_id": user_id,
                        "kind": kind,
                        "id": item_id,
                        "field": field,
                        "json": json_projection[field],
                        "postgres": postgres_projection[field],
                    }
                )


def reconcile_audio_studio(
    data_root: str | Path,
    repository_factory: RepositoryFactory,
) -> dict:
    """Compare file-backed audio studio state with PostgreSQL shadow data."""

    json_tasks_by_user, json_profiles_by_user, load_failures = _load_json_state(data_root)
    users = sorted(set(json_tasks_by_user) | set(json_profiles_by_user))

    missing_in_postgres: list[dict] = []
    missing_in_json: list[dict] = []
    field_differences: list[dict] = []
    postgres_task_count = 0
    postgres_voice_profile_count = 0

    for user_id in users:
        repository = repository_factory(user_id)
        postgres_tasks = {task.id: task for task in repository.list_all_tasks()}
        postgres_profiles = {
            profile.id: profile
            for profile in repository.list_all_voice_profiles()
        }
        postgres_task_count += len(postgres_tasks)
        postgres_voice_profile_count += len(postgres_profiles)

        _reconcile_collection(
            user_id=user_id,
            kind="audio_studio_task",
            json_items=json_tasks_by_user.get(user_id, {}),
            postgres_items=postgres_tasks,
            compare_fields=TASK_SAFE_COMPARE_FIELDS,
            missing_in_postgres=missing_in_postgres,
            missing_in_json=missing_in_json,
            field_differences=field_differences,
        )
        _reconcile_collection(
            user_id=user_id,
            kind="voice_profile",
            json_items=json_profiles_by_user.get(user_id, {}),
            postgres_items=postgres_profiles,
            compare_fields=VOICE_PROFILE_SAFE_COMPARE_FIELDS,
            missing_in_postgres=missing_in_postgres,
            missing_in_json=missing_in_json,
            field_differences=field_differences,
        )

    summary = {
        "domain": "audio_studio",
        "json_task_count": sum(len(items) for items in json_tasks_by_user.values()),
        "postgres_task_count": postgres_task_count,
        "json_voice_profile_count": sum(len(items) for items in json_profiles_by_user.values()),
        "postgres_voice_profile_count": postgres_voice_profile_count,
        "missing_in_postgres": missing_in_postgres,
        "missing_in_json": missing_in_json,
        "field_differences": field_differences,
        "load_failures": load_failures,
    }
    summary["ok"] = not (
        missing_in_postgres
        or missing_in_json
        or field_differences
        or load_failures
    )
    return summary


def render_reconcile_markdown(summary: dict) -> str:
    """Render a sanitized human-readable audio studio reconcile summary."""

    lines = [
        "# Audio Studio Reconcile",
        "",
        f"- domain: `{summary['domain']}`",
        f"- ok: `{str(summary['ok']).lower()}`",
        f"- json_task_count: `{summary['json_task_count']}`",
        f"- postgres_task_count: `{summary['postgres_task_count']}`",
        f"- json_voice_profile_count: `{summary['json_voice_profile_count']}`",
        f"- postgres_voice_profile_count: `{summary['postgres_voice_profile_count']}`",
        f"- missing_in_postgres: `{len(summary['missing_in_postgres'])}`",
        f"- missing_in_json: `{len(summary['missing_in_json'])}`",
        f"- field_differences: `{len(summary['field_differences'])}`",
        f"- load_failures: `{len(summary.get('load_failures', []))}`",
        "",
    ]

    for key in ("missing_in_postgres", "missing_in_json", "field_differences", "load_failures"):
        items = summary.get(key, [])
        if not items:
            continue
        lines.append(f"## {key}")
        for item in items:
            if key == "field_differences":
                lines.append(
                    f"- user_id=`{item['user_id']}` kind=`{item['kind']}` id=`{item['id']}` field=`{item['field']}`"
                )
            elif key == "load_failures":
                lines.append(
                    f"- user_id=`{item['user_id']}` kind=`{item['kind']}` file=`{item['file']}` error=`{item['error']}`"
                )
            else:
                lines.append(
                    f"- user_id=`{item['user_id']}` kind=`{item['kind']}` id=`{item['id']}`"
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_reconcile_reports(summary: dict, output_dir: str | Path) -> tuple[Path, Path]:
    """Write sanitized JSON and Markdown reconcile summaries."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "audio_studio_reconcile.json"
    markdown_path = output_path / "audio_studio_reconcile.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    markdown_path.write_text(render_reconcile_markdown(summary), encoding="utf-8")
    return json_path, markdown_path
