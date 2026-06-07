"""Reconcile JSON and PostgreSQL project state."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.project import Project
from app.services.migration.backfill_projects import (
    RepositoryFactory,
    iter_project_json_files,
)


SAFE_COMPARE_FIELDS = (
    "updated_at",
    "script_shot_count",
    "character_count",
    "scene_count",
    "prop_count",
    "style_count",
)


def _safe_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _project_safe_projection(project: Project) -> dict[str, Any]:
    return {
        "updated_at": _safe_value(project.updated_at),
        "script_shot_count": len(project.script.shots) if project.script else 0,
        "character_count": len(project.character_ids or []),
        "scene_count": len(project.scene_ids or []),
        "prop_count": len(project.prop_ids or []),
        "style_count": len(project.style_ids or []),
    }


def reconcile_projects(
    data_root: str | Path,
    repository_factory: RepositoryFactory,
) -> dict:
    """Compare JSON primary project data with PostgreSQL shadow data."""

    json_by_user: dict[str, dict[str, Project]] = {}
    load_failures: list[dict] = []

    def record_load_failure(user_id: str, project_path: Path, exc: Exception) -> None:
        load_failures.append(
            {
                "user_id": user_id,
                "project_file": project_path.name,
                "error": exc.__class__.__name__,
            }
        )

    for record in iter_project_json_files(data_root, on_error=record_load_failure):
        json_by_user.setdefault(record.user_id, {})[record.project.id] = record.project

    missing_in_postgres: list[dict] = []
    missing_in_json: list[dict] = []
    field_differences: list[dict] = []
    postgres_count = 0

    for user_id in sorted(json_by_user):
        json_projects = json_by_user[user_id]
        postgres_projects = {
            project.id: project for project in repository_factory(user_id).list_all()
        }
        postgres_count += len(postgres_projects)

        for project_id in sorted(set(json_projects) - set(postgres_projects)):
            missing_in_postgres.append({"user_id": user_id, "project_id": project_id})

        for project_id in sorted(set(postgres_projects) - set(json_projects)):
            missing_in_json.append({"user_id": user_id, "project_id": project_id})

        for project_id in sorted(set(json_projects) & set(postgres_projects)):
            json_projection = _project_safe_projection(json_projects[project_id])
            postgres_projection = _project_safe_projection(postgres_projects[project_id])
            for field in SAFE_COMPARE_FIELDS:
                if json_projection[field] != postgres_projection[field]:
                    field_differences.append(
                        {
                            "user_id": user_id,
                            "project_id": project_id,
                            "field": field,
                        }
                    )

    summary = {
        "domain": "projects",
        "json_count": sum(len(projects) for projects in json_by_user.values()),
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
        "# Projects Reconcile",
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
                    f"- user_id=`{item['user_id']}` project_id=`{item['project_id']}` field=`{item['field']}`"
                )
            elif key == "load_failures":
                lines.append(
                    f"- user_id=`{item['user_id']}` project_file=`{item['project_file']}` error=`{item['error']}`"
                )
            else:
                lines.append(
                    f"- user_id=`{item['user_id']}` project_id=`{item['project_id']}`"
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_reconcile_reports(summary: dict, output_dir: str | Path) -> tuple[Path, Path]:
    """Write sanitized JSON and Markdown reconcile summaries."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "projects_reconcile.json"
    markdown_path = output_path / "projects_reconcile.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    markdown_path.write_text(render_reconcile_markdown(summary), encoding="utf-8")
    return json_path, markdown_path
