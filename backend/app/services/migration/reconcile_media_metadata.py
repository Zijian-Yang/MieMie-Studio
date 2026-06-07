"""Reconcile JSON and PostgreSQL media metadata state."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.gallery import GalleryImage
from app.models.media import AudioItem, TextItem, VideoItem
from app.services.migration.backfill_media_metadata import (
    DOMAIN_ORDER,
    MediaRepositoryFactory,
    TextRepositoryFactory,
    iter_media_metadata_json_files,
)


MediaMetadataItem = GalleryImage | AudioItem | VideoItem | TextItem

SAFE_COMPARE_FIELDS = {
    "gallery": ("updated_at",),
    "audio": ("updated_at", "file_size", "duration"),
    "video_library": ("updated_at", "file_size", "duration", "width", "height", "fps"),
    "text_library": ("updated_at", "version_count"),
}


def _safe_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _safe_projection(domain: str, item: MediaMetadataItem) -> dict[str, Any]:
    projection = {"updated_at": _safe_value(item.updated_at)}
    if isinstance(item, (AudioItem, VideoItem)):
        projection["file_size"] = item.file_size
        projection["duration"] = item.duration
    if isinstance(item, VideoItem):
        projection["width"] = item.width
        projection["height"] = item.height
        projection["fps"] = item.fps
    if isinstance(item, TextItem):
        projection["version_count"] = len(item.versions or [])
    return {
        field: projection[field]
        for field in SAFE_COMPARE_FIELDS[domain]
    }


def _postgres_items_by_domain(
    user_id: str,
    media_repository_factory: MediaRepositoryFactory,
    text_repository_factory: TextRepositoryFactory,
) -> dict[str, dict[str, MediaMetadataItem]]:
    media_repo = media_repository_factory(user_id)
    text_repo = text_repository_factory(user_id)
    return {
        "gallery": {item.id: item for item in media_repo.list_all_gallery_images()},
        "audio": {item.id: item for item in media_repo.list_all_audio_items()},
        "video_library": {item.id: item for item in media_repo.list_all_video_items()},
        "text_library": {item.id: item for item in text_repo.list_all()},
    }


def reconcile_media_metadata(
    data_root: str | Path,
    media_repository_factory: MediaRepositoryFactory,
    text_repository_factory: TextRepositoryFactory,
) -> dict:
    """Compare JSON primary media metadata with PostgreSQL shadow data."""

    json_by_user: dict[str, dict[str, dict[str, MediaMetadataItem]]] = {}
    load_failures: list[dict] = []

    def record_load_failure(user_id: str, domain: str, item_path: Path, exc: Exception) -> None:
        load_failures.append(
            {
                "user_id": user_id,
                "domain": domain,
                "item_file": item_path.name,
                "error": exc.__class__.__name__,
            }
        )

    for record in iter_media_metadata_json_files(data_root, on_error=record_load_failure):
        json_by_user.setdefault(record.user_id, {domain: {} for domain in DOMAIN_ORDER})
        json_by_user[record.user_id][record.domain][record.item.id] = record.item

    missing_in_postgres: list[dict] = []
    missing_in_json: list[dict] = []
    field_differences: list[dict] = []
    postgres_count_by_domain = {domain: 0 for domain in DOMAIN_ORDER}

    for user_id in sorted(json_by_user):
        postgres_by_domain = _postgres_items_by_domain(
            user_id,
            media_repository_factory,
            text_repository_factory,
        )

        for domain in DOMAIN_ORDER:
            json_items = json_by_user[user_id][domain]
            postgres_items = postgres_by_domain[domain]
            postgres_count_by_domain[domain] += len(postgres_items)

            for item_id in sorted(set(json_items) - set(postgres_items)):
                missing_in_postgres.append(
                    {"user_id": user_id, "domain": domain, "item_id": item_id}
                )

            for item_id in sorted(set(postgres_items) - set(json_items)):
                missing_in_json.append(
                    {"user_id": user_id, "domain": domain, "item_id": item_id}
                )

            for item_id in sorted(set(json_items) & set(postgres_items)):
                json_projection = _safe_projection(domain, json_items[item_id])
                postgres_projection = _safe_projection(domain, postgres_items[item_id])
                for field in SAFE_COMPARE_FIELDS[domain]:
                    if json_projection[field] != postgres_projection[field]:
                        field_differences.append(
                            {
                                "user_id": user_id,
                                "domain": domain,
                                "item_id": item_id,
                                "field": field,
                            }
                        )

    json_count_by_domain = {
        domain: sum(len(user_items.get(domain, {})) for user_items in json_by_user.values())
        for domain in DOMAIN_ORDER
    }
    summary = {
        "domain": "media_metadata",
        "json_count": sum(json_count_by_domain.values()),
        "postgres_count": sum(postgres_count_by_domain.values()),
        "json_count_by_domain": json_count_by_domain,
        "postgres_count_by_domain": postgres_count_by_domain,
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
        "# Media Metadata Reconcile",
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
                    f"- user_id=`{item['user_id']}` domain=`{item['domain']}` item_id=`{item['item_id']}` field=`{item['field']}`"
                )
            elif key == "load_failures":
                lines.append(
                    f"- user_id=`{item['user_id']}` domain=`{item['domain']}` item_file=`{item['item_file']}` error=`{item['error']}`"
                )
            else:
                lines.append(
                    f"- user_id=`{item['user_id']}` domain=`{item['domain']}` item_id=`{item['item_id']}`"
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_reconcile_reports(summary: dict, output_dir: str | Path) -> tuple[Path, Path]:
    """Write sanitized JSON and Markdown reconcile summaries."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "media_metadata_reconcile.json"
    markdown_path = output_path / "media_metadata_reconcile.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    markdown_path.write_text(render_reconcile_markdown(summary), encoding="utf-8")
    return json_path, markdown_path
