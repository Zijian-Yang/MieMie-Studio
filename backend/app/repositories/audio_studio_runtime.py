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
    raw_value = os.getenv(name, "").replace(",", " ")
    return {
        item.strip()
        for item in raw_value.split()
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


def audio_studio_read_enabled() -> bool:
    """Return true when audio studio reads should prefer PostgreSQL."""

    if not database_enabled():
        return False

    read_mode = os.getenv("MIEMIE_DATABASE_READ_MODE", "file").strip().lower()
    read_domains = _env_csv("MIEMIE_DATABASE_READ_DOMAINS")
    return read_mode == "postgres" or DOMAIN in read_domains


def audio_studio_primary_write_enabled() -> bool:
    """Return true when audio studio writes should use PostgreSQL primary."""

    if not database_enabled():
        return False

    write_mode = os.getenv("MIEMIE_DATABASE_WRITE_MODE", "file").strip().lower()
    primary_domains = _env_csv("MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS")
    return write_mode in {"postgres", "postgres_primary", "primary"} or DOMAIN in primary_domains


def json_archive_writes_enabled() -> bool:
    """Return true when PostgreSQL primary writes should maintain JSON archive mirrors."""

    return _env_true("MIEMIE_DATABASE_JSON_ARCHIVE_WRITES")


def json_fallback_read_enabled() -> bool:
    """Return true when PostgreSQL read miss/error should fallback to JSON."""

    return _env_true("MIEMIE_DATABASE_JSON_FALLBACK_READ")


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


def build_audio_studio_read_repository(user_id: str) -> PostgresAudioStudioRepository:
    return PostgresAudioStudioRepository(_runtime_engine(), user_id)


def build_audio_studio_primary_repository(user_id: str) -> PostgresAudioStudioRepository:
    return PostgresAudioStudioRepository(_runtime_engine(), user_id)


def save_audio_studio_task_primary(user_id: str | None, task: AudioStudioTask) -> bool:
    """Save an audio studio task to PostgreSQL as primary when primary mode is enabled."""

    if not user_id or not audio_studio_primary_write_enabled():
        return False

    build_audio_studio_primary_repository(user_id).save_task(task)
    return True


def mark_audio_studio_task_deleted_primary(user_id: str | None, task_id: str) -> bool:
    """Mark a PostgreSQL-primary audio studio task deleted when primary mode is enabled."""

    if not user_id or not audio_studio_primary_write_enabled():
        return False

    build_audio_studio_primary_repository(user_id).mark_task_deleted(task_id)
    return True


def save_voice_profile_primary(user_id: str | None, profile: VoiceProfile) -> bool:
    """Save a voice profile to PostgreSQL as primary when primary mode is enabled."""

    if not user_id or not audio_studio_primary_write_enabled():
        return False

    build_audio_studio_primary_repository(user_id).save_voice_profile(profile)
    return True


def mark_voice_profile_deleted_primary(user_id: str | None, profile_id: str) -> bool:
    """Mark a PostgreSQL-primary voice profile deleted when primary mode is enabled."""

    if not user_id or not audio_studio_primary_write_enabled():
        return False

    build_audio_studio_primary_repository(user_id).mark_voice_profile_deleted(profile_id)
    return True


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


def read_audio_studio_task(
    user_id: str | None,
    task_id: str,
    json_loader,
) -> AudioStudioTask | None:
    """Read one audio studio task from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not audio_studio_read_enabled():
        return json_loader()

    try:
        task = build_audio_studio_read_repository(user_id).get_task(task_id)
        if task is not None:
            return task
        if json_fallback_read_enabled():
            logger.warning(
                "audio_studio_task_postgres_read_miss_json_fallback",
                extra={"user_id": user_id, "task_id": task_id},
            )
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "audio_studio_task_postgres_read_failed_json_fallback",
            extra={"user_id": user_id, "task_id": task_id, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_audio_studio_tasks_for_project(
    user_id: str | None,
    project_id: str,
    json_loader,
) -> list[AudioStudioTask]:
    """Read project audio studio tasks from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not audio_studio_read_enabled():
        return json_loader()

    try:
        tasks = build_audio_studio_read_repository(user_id).list_tasks_for_project(project_id)
        if tasks or not json_fallback_read_enabled():
            return tasks
        logger.warning(
            "audio_studio_task_postgres_project_empty_json_fallback",
            extra={"user_id": user_id, "project_id": project_id},
        )
        return json_loader()
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "audio_studio_task_postgres_project_read_failed_json_fallback",
            extra={"user_id": user_id, "project_id": project_id, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_voice_profile(
    user_id: str | None,
    profile_id: str,
    json_loader,
) -> VoiceProfile | None:
    """Read one voice profile from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not audio_studio_read_enabled():
        return json_loader()

    try:
        profile = build_audio_studio_read_repository(user_id).get_voice_profile(profile_id)
        if profile is not None:
            return profile
        if json_fallback_read_enabled():
            logger.warning(
                "voice_profile_postgres_read_miss_json_fallback",
                extra={"user_id": user_id, "profile_id": profile_id},
            )
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "voice_profile_postgres_read_failed_json_fallback",
            extra={"user_id": user_id, "profile_id": profile_id, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_voice_profiles_for_project(
    user_id: str | None,
    project_id: str,
    json_loader,
) -> list[VoiceProfile]:
    """Read project voice profiles from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not audio_studio_read_enabled():
        return json_loader()

    try:
        profiles = build_audio_studio_read_repository(user_id).list_voice_profiles_for_project(project_id)
        if profiles or not json_fallback_read_enabled():
            return profiles
        logger.warning(
            "voice_profile_postgres_project_empty_json_fallback",
            extra={"user_id": user_id, "project_id": project_id},
        )
        return json_loader()
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "voice_profile_postgres_project_read_failed_json_fallback",
            extra={"user_id": user_id, "project_id": project_id, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_voice_profile_by_voice_id(
    user_id: str | None,
    voice_id: str,
    json_loader,
) -> VoiceProfile | None:
    """Read one voice profile by DashScope voice id with optional JSON fallback."""

    if not user_id or not audio_studio_read_enabled():
        return json_loader()

    try:
        profile = build_audio_studio_read_repository(user_id).get_voice_profile_by_voice_id(voice_id)
        if profile is not None:
            return profile
        if json_fallback_read_enabled():
            logger.warning(
                "voice_profile_postgres_voice_id_miss_json_fallback",
                extra={"user_id": user_id, "voice_id": voice_id},
            )
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "voice_profile_postgres_voice_id_read_failed_json_fallback",
            extra={"user_id": user_id, "voice_id": voice_id, "error": exc.__class__.__name__},
        )
        return json_loader()
