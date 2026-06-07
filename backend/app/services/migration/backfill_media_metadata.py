"""Backfill media library JSON files into PostgreSQL repositories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from app.models.gallery import GalleryImage
from app.models.media import AudioItem, TextItem, VideoItem
from app.repositories.base import MediaAssetRepository, TextItemRepository


MediaRepositoryFactory = Callable[[str], MediaAssetRepository]
TextRepositoryFactory = Callable[[str], TextItemRepository]
MediaMetadataItem = GalleryImage | AudioItem | VideoItem | TextItem

DOMAIN_MODELS: dict[str, type[MediaMetadataItem]] = {
    "gallery": GalleryImage,
    "audio": AudioItem,
    "video_library": VideoItem,
    "text_library": TextItem,
}

DOMAIN_ORDER = ("gallery", "audio", "video_library", "text_library")


@dataclass(frozen=True)
class MediaMetadataJsonRecord:
    user_id: str
    domain: str
    item: MediaMetadataItem
    source_path: Path


def iter_media_metadata_json_files(
    data_root: str | Path,
    *,
    on_error: Optional[Callable[[str, str, Path, Exception], None]] = None,
) -> Iterable[MediaMetadataJsonRecord]:
    """Yield valid per-user media metadata records from JSON libraries."""

    users_dir = Path(data_root) / "users"
    if not users_dir.exists():
        return

    for user_dir in sorted(path for path in users_dir.iterdir() if path.is_dir()):
        for domain in DOMAIN_ORDER:
            item_dir = user_dir / domain
            if not item_dir.exists():
                continue
            model = DOMAIN_MODELS[domain]
            for item_path in sorted(item_dir.glob("*.json")):
                try:
                    with item_path.open("r", encoding="utf-8") as handle:
                        data = json.load(handle)
                    yield MediaMetadataJsonRecord(
                        user_id=user_dir.name,
                        domain=domain,
                        item=model(**data),
                        source_path=item_path,
                    )
                except Exception as exc:
                    if on_error:
                        on_error(user_dir.name, domain, item_path, exc)


def _save_record(
    record: MediaMetadataJsonRecord,
    media_repository_factory: MediaRepositoryFactory,
    text_repository_factory: TextRepositoryFactory,
) -> None:
    if record.domain == "gallery":
        media_repository_factory(record.user_id).save_gallery_image(record.item)
    elif record.domain == "audio":
        media_repository_factory(record.user_id).save_audio_item(record.item)
    elif record.domain == "video_library":
        media_repository_factory(record.user_id).save_video_item(record.item)
    elif record.domain == "text_library":
        text_repository_factory(record.user_id).save(record.item)
    else:
        raise ValueError(f"Unsupported media metadata domain: {record.domain}")


def backfill_media_metadata(
    data_root: str | Path,
    media_repository_factory: MediaRepositoryFactory,
    text_repository_factory: TextRepositoryFactory,
) -> dict:
    """Upsert all valid per-user media metadata JSON into PostgreSQL."""

    failures: list[dict] = []
    scanned_users: set[str] = set()
    counts_by_domain = {domain: 0 for domain in DOMAIN_ORDER}
    upserted_count = 0

    def record_load_failure(user_id: str, domain: str, item_path: Path, exc: Exception) -> None:
        failures.append(
            {
                "user_id": user_id,
                "domain": domain,
                "item_file": item_path.name,
                "error": exc.__class__.__name__,
            }
        )

    for record in iter_media_metadata_json_files(data_root, on_error=record_load_failure):
        scanned_users.add(record.user_id)
        counts_by_domain[record.domain] += 1
        try:
            _save_record(record, media_repository_factory, text_repository_factory)
            upserted_count += 1
        except Exception as exc:
            failures.append(
                {
                    "user_id": record.user_id,
                    "domain": record.domain,
                    "item_id": record.item.id,
                    "error": exc.__class__.__name__,
                }
            )

    json_count = sum(counts_by_domain.values())
    return {
        "domain": "media_metadata",
        "scanned_users": sorted(scanned_users),
        "json_count": json_count,
        "json_count_by_domain": counts_by_domain,
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
