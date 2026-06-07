"""Reconcile JSON and PostgreSQL project editing entity state."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.video import Video
from app.services.migration.backfill_project_entities import (
    ENTITY_ORDER,
    ProjectEntityItem,
    RepositoryFactory,
    iter_project_entity_json_files,
)


SAFE_COMPARE_FIELDS = {
    "character": ("updated_at", "project_id", "selected_group_index"),
    "scene": ("updated_at", "project_id", "selected_group_index"),
    "prop": ("updated_at", "project_id", "selected_group_index"),
    "frame": ("updated_at", "project_id", "shot_id", "shot_number", "selected_group_index"),
    "video": ("updated_at", "project_id", "shot_id", "shot_number", "status"),
    "style": ("updated_at", "project_id", "selected_group_index"),
}


def _safe_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _video_status(entity: ProjectEntityItem) -> str | None:
    if not isinstance(entity, Video) or not entity.task:
        return None
    status = entity.task.status
    return getattr(status, "value", status)


def _safe_projection(entity_kind: str, entity: ProjectEntityItem) -> dict[str, Any]:
    projection = {
        "updated_at": _safe_value(entity.updated_at),
        "project_id": entity.project_id,
        "selected_group_index": getattr(entity, "selected_group_index", 0),
        "shot_id": getattr(entity, "shot_id", None),
        "shot_number": getattr(entity, "shot_number", None),
        "status": _video_status(entity),
    }
    return {
        field: projection[field]
        for field in SAFE_COMPARE_FIELDS[entity_kind]
    }


def reconcile_project_entities(
    data_root: str | Path,
    repository_factory: RepositoryFactory,
) -> dict:
    """Compare JSON primary project editing entities with PostgreSQL shadow data."""

    json_by_user: dict[str, dict[str, dict[str, ProjectEntityItem]]] = {}
    load_failures: list[dict] = []

    def record_load_failure(user_id: str, entity_kind: str, entity_path: Path, exc: Exception) -> None:
        load_failures.append(
            {
                "user_id": user_id,
                "entity_kind": entity_kind,
                "entity_file": entity_path.name,
                "error": exc.__class__.__name__,
            }
        )

    for record in iter_project_entity_json_files(data_root, on_error=record_load_failure):
        json_by_user.setdefault(user_id := record.user_id, {kind: {} for kind in ENTITY_ORDER})
        json_by_user[user_id][record.entity_kind][record.entity.id] = record.entity

    missing_in_postgres: list[dict] = []
    missing_in_json: list[dict] = []
    field_differences: list[dict] = []
    postgres_count_by_kind = {entity_kind: 0 for entity_kind in ENTITY_ORDER}

    for user_id in sorted(json_by_user):
        repository = repository_factory(user_id)
        postgres_by_kind = {
            entity_kind: {
                entity.id: entity
                for entity in repository.list_all(entity_kind)
            }
            for entity_kind in ENTITY_ORDER
        }

        for entity_kind in ENTITY_ORDER:
            json_items = json_by_user[user_id][entity_kind]
            postgres_items = postgres_by_kind[entity_kind]
            postgres_count_by_kind[entity_kind] += len(postgres_items)

            for entity_id in sorted(set(json_items) - set(postgres_items)):
                missing_in_postgres.append(
                    {"user_id": user_id, "entity_kind": entity_kind, "entity_id": entity_id}
                )

            for entity_id in sorted(set(postgres_items) - set(json_items)):
                missing_in_json.append(
                    {"user_id": user_id, "entity_kind": entity_kind, "entity_id": entity_id}
                )

            for entity_id in sorted(set(json_items) & set(postgres_items)):
                json_projection = _safe_projection(entity_kind, json_items[entity_id])
                postgres_projection = _safe_projection(entity_kind, postgres_items[entity_id])
                for field in SAFE_COMPARE_FIELDS[entity_kind]:
                    if json_projection[field] != postgres_projection[field]:
                        field_differences.append(
                            {
                                "user_id": user_id,
                                "entity_kind": entity_kind,
                                "entity_id": entity_id,
                                "field": field,
                            }
                        )

    json_count_by_kind = {
        entity_kind: sum(len(user_items.get(entity_kind, {})) for user_items in json_by_user.values())
        for entity_kind in ENTITY_ORDER
    }
    summary = {
        "domain": "project_entities",
        "json_count": sum(json_count_by_kind.values()),
        "postgres_count": sum(postgres_count_by_kind.values()),
        "json_count_by_kind": json_count_by_kind,
        "postgres_count_by_kind": postgres_count_by_kind,
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
        "# Project Entities Reconcile",
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
                    f"- user_id=`{item['user_id']}` entity_kind=`{item['entity_kind']}` entity_id=`{item['entity_id']}` field=`{item['field']}`"
                )
            elif key == "load_failures":
                lines.append(
                    f"- user_id=`{item['user_id']}` entity_kind=`{item['entity_kind']}` entity_file=`{item['entity_file']}` error=`{item['error']}`"
                )
            else:
                lines.append(
                    f"- user_id=`{item['user_id']}` entity_kind=`{item['entity_kind']}` entity_id=`{item['entity_id']}`"
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_reconcile_reports(summary: dict, output_dir: str | Path) -> tuple[Path, Path]:
    """Write sanitized JSON and Markdown reconcile summaries."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "project_entities_reconcile.json"
    markdown_path = output_path / "project_entities_reconcile.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    markdown_path.write_text(render_reconcile_markdown(summary), encoding="utf-8")
    return json_path, markdown_path
