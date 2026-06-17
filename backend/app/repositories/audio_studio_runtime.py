"""Runtime feature flags for audio studio PostgreSQL shadow writes."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from sqlalchemy.pool import NullPool

from app.db.engine import TRUE_VALUES, create_database_engine, database_enabled
from app.models.audio_studio import AudioStudioTask, VoiceProfile
from app.repositories.audio_studio import PostgresAudioStudioRepository


logger = logging.getLogger(__name__)

DOMAIN = "audio_studio"


def _env_csv(name: str) -> set[str]:
    return {
        item.strip()
        for item in os.getenv(name, "").split(",")
        if item.strip()
    }


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def audio_studio_dual_write_enabled() -> bool:
    """Return true when audio studio shadow writes are explicitly enabled."""

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


def build_audio_studio_shadow_repository(user_id: str) -> PostgresAudioStudioRepository:
    return PostgresAudioStudioRepository(_runtime_engine(), user_id)


def shadow_save_audio_studio_task(user_id: str | None, task: AudioStudioTask) -> None:
    """Shadow-save an audio studio task to PostgreSQL when dual-write is enabled."""

    if not user_id or not audio_studio_dual_write_enabled():
        return

    try:
        build_audio_studio_shadow_repository(user_id).save_task(task)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "audio_studio_task_runtime_shadow_save_failed",
            extra={"user_id": user_id, "task_id": task.id, "error": exc.__class__.__name__},
        )


def shadow_mark_audio_studio_task_deleted(user_id: str | None, task_id: str) -> None:
    """Shadow-mark an audio studio task deleted in PostgreSQL when dual-write is enabled."""

    if not user_id or not audio_studio_dual_write_enabled():
        return

    try:
        build_audio_studio_shadow_repository(user_id).mark_task_deleted(task_id)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "audio_studio_task_runtime_shadow_delete_failed",
            extra={"user_id": user_id, "task_id": task_id, "error": exc.__class__.__name__},
        )


def shadow_save_voice_profile(user_id: str | None, profile: VoiceProfile) -> None:
    """Shadow-save a voice profile to PostgreSQL when dual-write is enabled."""

    if not user_id or not audio_studio_dual_write_enabled():
        return

    try:
        build_audio_studio_shadow_repository(user_id).save_voice_profile(profile)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "voice_profile_runtime_shadow_save_failed",
            extra={"user_id": user_id, "profile_id": profile.id, "error": exc.__class__.__name__},
        )


def shadow_mark_voice_profile_deleted(user_id: str | None, profile_id: str) -> None:
    """Shadow-mark a voice profile deleted in PostgreSQL when dual-write is enabled."""

    if not user_id or not audio_studio_dual_write_enabled():
        return

    try:
        build_audio_studio_shadow_repository(user_id).mark_voice_profile_deleted(profile_id)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "voice_profile_runtime_shadow_delete_failed",
            extra={"user_id": user_id, "profile_id": profile_id, "error": exc.__class__.__name__},
        )
