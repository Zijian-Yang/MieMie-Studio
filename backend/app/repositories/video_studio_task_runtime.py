"""Runtime feature flags for video studio task PostgreSQL shadow writes."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from sqlalchemy.pool import NullPool

from app.db.engine import TRUE_VALUES, create_database_engine, database_enabled
from app.models.media import VideoStudioTask
from app.repositories.video_studio_tasks import PostgresVideoStudioTaskRepository


logger = logging.getLogger(__name__)

DOMAIN = "video_studio_tasks"


def _env_csv(name: str) -> set[str]:
    return {
        item.strip()
        for item in os.getenv(name, "").split(",")
        if item.strip()
    }


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def video_studio_task_dual_write_enabled() -> bool:
    """Return true when video studio task shadow writes are explicitly enabled."""

    if not database_enabled():
        return False

    write_mode = os.getenv("MIEMIE_DATABASE_WRITE_MODE", "file").strip().lower()
    dual_domains = _env_csv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS")
    return write_mode == "dual" or DOMAIN in dual_domains


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


def build_video_studio_task_shadow_repository(user_id: str) -> PostgresVideoStudioTaskRepository:
    return PostgresVideoStudioTaskRepository(_runtime_engine(), user_id)


def shadow_save_video_studio_task(user_id: str | None, task: VideoStudioTask) -> None:
    """Shadow-save a task to PostgreSQL when dual-write is enabled."""

    if not user_id or not video_studio_task_dual_write_enabled():
        return

    try:
        build_video_studio_task_shadow_repository(user_id).save(task)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "video_studio_task_runtime_shadow_save_failed",
            extra={"user_id": user_id, "task_id": task.id, "error": exc.__class__.__name__},
        )


def shadow_mark_video_studio_task_deleted(user_id: str | None, task_id: str) -> None:
    """Shadow-mark a task deleted in PostgreSQL when dual-write is enabled."""

    if not user_id or not video_studio_task_dual_write_enabled():
        return

    try:
        build_video_studio_task_shadow_repository(user_id).mark_deleted(task_id)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "video_studio_task_runtime_shadow_delete_failed",
            extra={"user_id": user_id, "task_id": task_id, "error": exc.__class__.__name__},
        )

