"""Runtime feature flags for media metadata PostgreSQL shadow writes."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from sqlalchemy.pool import NullPool

from app.db.engine import TRUE_VALUES, create_database_engine, database_enabled
from app.models.gallery import GalleryImage
from app.models.media import AudioItem, TextItem, VideoItem
from app.repositories.media_assets import PostgresMediaAssetRepository, PostgresTextItemRepository


logger = logging.getLogger(__name__)

DOMAIN = "media_metadata"


def _env_csv(name: str) -> set[str]:
    return {
        item.strip()
        for item in os.getenv(name, "").split(",")
        if item.strip()
    }


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def media_metadata_dual_write_enabled() -> bool:
    """Return true when media metadata shadow writes are explicitly enabled."""

    if not database_enabled():
        return False

    write_mode = os.getenv("MIEMIE_DATABASE_WRITE_MODE", "file").strip().lower()
    dual_domains = _env_csv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS")
    return write_mode in {"dual", "dual_write"} or DOMAIN in dual_domains


def media_metadata_primary_write_enabled() -> bool:
    """Return true when media metadata writes should use PostgreSQL primary."""

    if not database_enabled():
        return False

    write_mode = os.getenv("MIEMIE_DATABASE_WRITE_MODE", "file").strip().lower()
    primary_domains = _env_csv("MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS")
    return write_mode in {"postgres", "postgres_primary", "primary"} or DOMAIN in primary_domains


def media_metadata_read_enabled() -> bool:
    """Return true when media metadata reads should prefer PostgreSQL."""

    if not database_enabled():
        return False

    read_mode = os.getenv("MIEMIE_DATABASE_READ_MODE", "file").strip().lower()
    read_domains = _env_csv("MIEMIE_DATABASE_READ_DOMAINS")
    return read_mode == "postgres" or DOMAIN in read_domains


def json_fallback_read_enabled() -> bool:
    """Return true when PostgreSQL read miss/error should fallback to JSON."""

    return _env_true("MIEMIE_DATABASE_JSON_FALLBACK_READ")


def json_archive_writes_enabled() -> bool:
    """Return true when PostgreSQL primary writes should maintain JSON archive mirrors."""

    return _env_true("MIEMIE_DATABASE_JSON_ARCHIVE_WRITES")


def strict_shadow_writes_enabled() -> bool:
    """Return true when PostgreSQL shadow write failures should be propagated."""

    return _env_true("MIEMIE_DATABASE_RECONCILE_STRICT")


@lru_cache(maxsize=1)
def _runtime_engine():
    return create_database_engine(poolclass=NullPool, pool_pre_ping=True)


def clear_runtime_database_engine() -> None:
    """Dispose and clear the cached runtime engine, mainly for tests and shutdown hooks."""

    engine = _runtime_engine.cache_info().currsize and _runtime_engine()
    if engine:
        engine.dispose()
    _runtime_engine.cache_clear()


def build_media_asset_shadow_repository(user_id: str) -> PostgresMediaAssetRepository:
    return PostgresMediaAssetRepository(_runtime_engine(), user_id)


def build_text_item_shadow_repository(user_id: str) -> PostgresTextItemRepository:
    return PostgresTextItemRepository(_runtime_engine(), user_id)


def build_media_asset_read_repository(user_id: str) -> PostgresMediaAssetRepository:
    return PostgresMediaAssetRepository(_runtime_engine(), user_id)


def build_text_item_read_repository(user_id: str) -> PostgresTextItemRepository:
    return PostgresTextItemRepository(_runtime_engine(), user_id)


def build_media_asset_primary_repository(user_id: str) -> PostgresMediaAssetRepository:
    return PostgresMediaAssetRepository(_runtime_engine(), user_id)


def build_text_item_primary_repository(user_id: str) -> PostgresTextItemRepository:
    return PostgresTextItemRepository(_runtime_engine(), user_id)


def save_gallery_image_primary(user_id: str | None, image: GalleryImage) -> bool:
    """Save a gallery image to PostgreSQL as the primary store when enabled."""

    if not user_id or not media_metadata_primary_write_enabled():
        return False

    build_media_asset_primary_repository(user_id).save_gallery_image(image)
    return True


def save_audio_item_primary(user_id: str | None, audio: AudioItem) -> bool:
    """Save an audio item to PostgreSQL as the primary store when enabled."""

    if not user_id or not media_metadata_primary_write_enabled():
        return False

    build_media_asset_primary_repository(user_id).save_audio_item(audio)
    return True


def save_video_item_primary(user_id: str | None, video: VideoItem) -> bool:
    """Save a video item to PostgreSQL as the primary store when enabled."""

    if not user_id or not media_metadata_primary_write_enabled():
        return False

    build_media_asset_primary_repository(user_id).save_video_item(video)
    return True


def save_text_item_primary(user_id: str | None, item: TextItem) -> bool:
    """Save a text item to PostgreSQL as the primary store when enabled."""

    if not user_id or not media_metadata_primary_write_enabled():
        return False

    build_text_item_primary_repository(user_id).save(item)
    return True


def mark_media_asset_deleted_primary(user_id: str | None, asset_id: str) -> bool:
    """Mark a gallery/audio/video row deleted in PostgreSQL primary mode."""

    if not user_id or not media_metadata_primary_write_enabled():
        return False

    build_media_asset_primary_repository(user_id).mark_deleted(asset_id)
    return True


def mark_text_item_deleted_primary(user_id: str | None, item_id: str) -> bool:
    """Mark a text row deleted in PostgreSQL primary mode."""

    if not user_id or not media_metadata_primary_write_enabled():
        return False

    build_text_item_primary_repository(user_id).mark_deleted(item_id)
    return True


def shadow_save_gallery_image(user_id: str | None, image: GalleryImage) -> None:
    """Shadow-save a gallery image to PostgreSQL when dual-write is enabled."""

    if not user_id or not media_metadata_dual_write_enabled():
        return

    try:
        build_media_asset_shadow_repository(user_id).save_gallery_image(image)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "media_metadata_shadow_save_gallery_failed",
            extra={"user_id": user_id, "asset_id": image.id, "error": exc.__class__.__name__},
        )


def shadow_save_audio_item(user_id: str | None, audio: AudioItem) -> None:
    """Shadow-save an audio library item to PostgreSQL when dual-write is enabled."""

    if not user_id or not media_metadata_dual_write_enabled():
        return

    try:
        build_media_asset_shadow_repository(user_id).save_audio_item(audio)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "media_metadata_shadow_save_audio_failed",
            extra={"user_id": user_id, "asset_id": audio.id, "error": exc.__class__.__name__},
        )


def shadow_save_video_item(user_id: str | None, video: VideoItem) -> None:
    """Shadow-save a video library item to PostgreSQL when dual-write is enabled."""

    if not user_id or not media_metadata_dual_write_enabled():
        return

    try:
        build_media_asset_shadow_repository(user_id).save_video_item(video)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "media_metadata_shadow_save_video_failed",
            extra={"user_id": user_id, "asset_id": video.id, "error": exc.__class__.__name__},
        )


def shadow_save_text_item(user_id: str | None, item: TextItem) -> None:
    """Shadow-save a text library item to PostgreSQL when dual-write is enabled."""

    if not user_id or not media_metadata_dual_write_enabled():
        return

    try:
        build_text_item_shadow_repository(user_id).save(item)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "media_metadata_shadow_save_text_failed",
            extra={"user_id": user_id, "item_id": item.id, "error": exc.__class__.__name__},
        )


def shadow_mark_media_asset_deleted(user_id: str | None, asset_id: str) -> None:
    """Shadow-mark a gallery/audio/video metadata row deleted when dual-write is enabled."""

    if not user_id or not media_metadata_dual_write_enabled():
        return

    try:
        build_media_asset_shadow_repository(user_id).mark_deleted(asset_id)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "media_metadata_shadow_delete_asset_failed",
            extra={"user_id": user_id, "asset_id": asset_id, "error": exc.__class__.__name__},
        )


def shadow_mark_text_item_deleted(user_id: str | None, item_id: str) -> None:
    """Shadow-mark a text metadata row deleted when dual-write is enabled."""

    if not user_id or not media_metadata_dual_write_enabled():
        return

    try:
        build_text_item_shadow_repository(user_id).mark_deleted(item_id)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "media_metadata_shadow_delete_text_failed",
            extra={"user_id": user_id, "item_id": item_id, "error": exc.__class__.__name__},
        )


def read_gallery_image(user_id: str | None, image_id: str, json_loader) -> GalleryImage | None:
    """Read one gallery image from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not media_metadata_read_enabled():
        return json_loader()

    try:
        image = build_media_asset_read_repository(user_id).get_gallery_image(image_id)
        if image is not None:
            return image
        if json_fallback_read_enabled():
            logger.warning(
                "media_metadata_gallery_read_miss_json_fallback",
                extra={"user_id": user_id, "asset_id": image_id},
            )
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "media_metadata_gallery_read_failed_json_fallback",
            extra={"user_id": user_id, "asset_id": image_id, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_gallery_images_for_project(user_id: str | None, project_id: str, json_loader) -> list[GalleryImage]:
    """Read project gallery images from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not media_metadata_read_enabled():
        return json_loader()

    try:
        images = build_media_asset_read_repository(user_id).list_gallery_images_for_project(project_id)
        if images or not json_fallback_read_enabled():
            return images
        logger.warning(
            "media_metadata_gallery_list_empty_json_fallback",
            extra={"user_id": user_id, "project_id": project_id},
        )
        return json_loader()
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "media_metadata_gallery_list_failed_json_fallback",
            extra={"user_id": user_id, "project_id": project_id, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_audio_item(user_id: str | None, audio_id: str, json_loader) -> AudioItem | None:
    """Read one audio item from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not media_metadata_read_enabled():
        return json_loader()

    try:
        audio = build_media_asset_read_repository(user_id).get_audio_item(audio_id)
        if audio is not None:
            return audio
        if json_fallback_read_enabled():
            logger.warning(
                "media_metadata_audio_read_miss_json_fallback",
                extra={"user_id": user_id, "asset_id": audio_id},
            )
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "media_metadata_audio_read_failed_json_fallback",
            extra={"user_id": user_id, "asset_id": audio_id, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_audio_items_for_project(user_id: str | None, project_id: str, json_loader) -> list[AudioItem]:
    """Read project audio items from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not media_metadata_read_enabled():
        return json_loader()

    try:
        audios = build_media_asset_read_repository(user_id).list_audio_items_for_project(project_id)
        if audios or not json_fallback_read_enabled():
            return audios
        logger.warning(
            "media_metadata_audio_list_empty_json_fallback",
            extra={"user_id": user_id, "project_id": project_id},
        )
        return json_loader()
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "media_metadata_audio_list_failed_json_fallback",
            extra={"user_id": user_id, "project_id": project_id, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_video_item(user_id: str | None, video_id: str, json_loader) -> VideoItem | None:
    """Read one video item from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not media_metadata_read_enabled():
        return json_loader()

    try:
        video = build_media_asset_read_repository(user_id).get_video_item(video_id)
        if video is not None:
            return video
        if json_fallback_read_enabled():
            logger.warning(
                "media_metadata_video_read_miss_json_fallback",
                extra={"user_id": user_id, "asset_id": video_id},
            )
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "media_metadata_video_read_failed_json_fallback",
            extra={"user_id": user_id, "asset_id": video_id, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_video_items_for_project(user_id: str | None, project_id: str, json_loader) -> list[VideoItem]:
    """Read project video items from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not media_metadata_read_enabled():
        return json_loader()

    try:
        videos = build_media_asset_read_repository(user_id).list_video_items_for_project(project_id)
        if videos or not json_fallback_read_enabled():
            return videos
        logger.warning(
            "media_metadata_video_list_empty_json_fallback",
            extra={"user_id": user_id, "project_id": project_id},
        )
        return json_loader()
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "media_metadata_video_list_failed_json_fallback",
            extra={"user_id": user_id, "project_id": project_id, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_text_item(user_id: str | None, item_id: str, json_loader) -> TextItem | None:
    """Read one text item from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not media_metadata_read_enabled():
        return json_loader()

    try:
        item = build_text_item_read_repository(user_id).get(item_id)
        if item is not None:
            return item
        if json_fallback_read_enabled():
            logger.warning(
                "media_metadata_text_read_miss_json_fallback",
                extra={"user_id": user_id, "item_id": item_id},
            )
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "media_metadata_text_read_failed_json_fallback",
            extra={"user_id": user_id, "item_id": item_id, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_text_items_for_project(user_id: str | None, project_id: str, json_loader) -> list[TextItem]:
    """Read project text items from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not media_metadata_read_enabled():
        return json_loader()

    try:
        items = build_text_item_read_repository(user_id).list_for_project(project_id)
        if items or not json_fallback_read_enabled():
            return items
        logger.warning(
            "media_metadata_text_list_empty_json_fallback",
            extra={"user_id": user_id, "project_id": project_id},
        )
        return json_loader()
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "media_metadata_text_list_failed_json_fallback",
            extra={"user_id": user_id, "project_id": project_id, "error": exc.__class__.__name__},
        )
        return json_loader()
