"""Reconcile JSON and PostgreSQL image studio task state."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.studio import StudioTask
from app.services.migration.backfill_studio_tasks import (
    RepositoryFactory,
    iter_studio_json_tasks,
)


SAFE_COMPARE_FIELDS = ("project_id", "status", "updated_at", "last_task_id")


def _safe_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _task_safe_projection(task: StudioTask) -> dict[str, Any]:
    return {field: _safe_value(getattr(task, field, None)) for field in SAFE_COMPARE_FIELDS}


def reconcile_studio_tasks(
    data_root: str | Path,
    repository_factory: RepositoryFactory,
) -> dict:
    """Compare JSON primary data with PostgreSQL shadow data for scanned users."""

    json_by_user: dict[str, dict[str, StudioTask]] = {}
    load_failures: list[dict] = []

    def record_load_failure(user_id: str, task_path: Path, exc: Exception) -> None:
        load_failures.append(
            {
                "user_id": user_id,
                "task_file": task_path.name,
                "error": exc.__class__.__name__,
            }
        )

    for record in iter_studio_json_tasks(data_root, on_error=record_load_failure):
        json_by_user.setdefault(record.user_id, {})[record.task.id] = record.task

    missing_in_postgres: list[dict] = []
    missing_in_json: list[dict] = []
    field_differences: list[dict] = []
    postgres_count = 0

    for user_id in sorted(json_by_user):
        json_tasks = json_by_user[user_id]
        postgres_tasks = {
            task.id: task for task in repository_factory(user_id).list_all()
        }
        postgres_count += len(postgres_tasks)

        for task_id in sorted(set(json_tasks) - set(postgres_tasks)):
            missing_in_postgres.append({"user_id": user_id, "task_id": task_id})

        for task_id in sorted(set(postgres_tasks) - set(json_tasks)):
            missing_in_json.append({"user_id": user_id, "task_id": task_id})

        for task_id in sorted(set(json_tasks) & set(postgres_tasks)):
            json_projection = _task_safe_projection(json_tasks[task_id])
            postgres_projection = _task_safe_projection(postgres_tasks[task_id])
            for field in SAFE_COMPARE_FIELDS:
                if json_projection[field] != postgres_projection[field]:
                    field_differences.append(
                        {
                            "user_id": user_id,
                            "task_id": task_id,
                            "field": field,
                            "json": json_projection[field],
                            "postgres": postgres_projection[field],
                        }
                    )

    summary = {
        "domain": "studio_tasks",
        "json_count": sum(len(tasks) for tasks in json_by_user.values()),
        "postgres_count": postgres_count,
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
    """Render a sanitized human-readable reconcile summary."""

    lines = [
        "# Studio Tasks Reconcile",
        "",
        f"- domain: `{summary['domain']}`",
        f"- ok: `{str(summary['ok']).lower()}`",
        f"- json_count: `{summary['json_count']}`",
        f"- postgres_count: `{summary['postgres_count']}`",
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
                    f"- user_id=`{item['user_id']}` task_id=`{item['task_id']}` field=`{item['field']}`"
                )
            elif key == "load_failures":
                lines.append(
                    f"- user_id=`{item['user_id']}` task_file=`{item['task_file']}` error=`{item['error']}`"
                )
            else:
                lines.append(
                    f"- user_id=`{item['user_id']}` task_id=`{item['task_id']}`"
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_reconcile_reports(summary: dict, output_dir: str | Path) -> tuple[Path, Path]:
    """Write sanitized JSON and Markdown reconcile summaries."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "studio_tasks_reconcile.json"
    markdown_path = output_path / "studio_tasks_reconcile.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    markdown_path.write_text(render_reconcile_markdown(summary), encoding="utf-8")
    return json_path, markdown_path
