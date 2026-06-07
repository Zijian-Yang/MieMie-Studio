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
