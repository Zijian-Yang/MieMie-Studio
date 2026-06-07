"""Runtime feature flags for image studio task PostgreSQL shadow writes."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from sqlalchemy.pool import NullPool

from app.db.engine import TRUE_VALUES, create_database_engine, database_enabled
from app.models.studio import StudioTask
from app.repositories.studio_tasks import PostgresStudioTaskRepository


logger = logging.getLogger(__name__)

DOMAIN = "studio_tasks"


def _env_csv(name: str) -> set[str]:
    return {
        item.strip()
        for item in os.getenv(name, "").split(",")
        if item.strip()
    }


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def studio_task_dual_write_enabled() -> bool:
    """Return true when image studio task shadow writes are explicitly enabled."""

    if not database_enabled():
        return False

    write_mode = os.getenv("MIEMIE_DATABASE_WRITE_MODE", "file").strip().lower()
    dual_domains = _env_csv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS")
    return write_mode in {"dual", "dual_write"} or DOMAIN in dual_domains


def studio_task_read_enabled() -> bool:
    """Return true when image studio task reads should prefer PostgreSQL."""

    if not database_enabled():
        return False

    read_mode = os.getenv("MIEMIE_DATABASE_READ_MODE", "file").strip().lower()
    read_domains = _env_csv("MIEMIE_DATABASE_READ_DOMAINS")
    return read_mode == "postgres" or DOMAIN in read_domains


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


def build_studio_task_shadow_repository(user_id: str) -> PostgresStudioTaskRepository:
    return PostgresStudioTaskRepository(_runtime_engine(), user_id)


def build_studio_task_read_repository(user_id: str) -> PostgresStudioTaskRepository:
    return PostgresStudioTaskRepository(_runtime_engine(), user_id)


def shadow_save_studio_task(user_id: str | None, task: StudioTask) -> None:
    """Shadow-save a task to PostgreSQL when dual-write is enabled."""

    if not user_id or not studio_task_dual_write_enabled():
        return

    try:
        build_studio_task_shadow_repository(user_id).save(task)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "studio_task_runtime_shadow_save_failed",
            extra={"user_id": user_id, "task_id": task.id, "error": exc.__class__.__name__},
        )


def shadow_mark_studio_task_deleted(user_id: str | None, task_id: str) -> None:
    """Shadow-mark a task deleted in PostgreSQL when dual-write is enabled."""

    if not user_id or not studio_task_dual_write_enabled():
        return

    try:
        build_studio_task_shadow_repository(user_id).mark_deleted(task_id)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "studio_task_runtime_shadow_delete_failed",
            extra={"user_id": user_id, "task_id": task_id, "error": exc.__class__.__name__},
        )


def read_studio_task(
    user_id: str | None,
    task_id: str,
    json_loader,
) -> StudioTask | None:
    """Read one task from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not studio_task_read_enabled():
        return json_loader()

    try:
        task = build_studio_task_read_repository(user_id).get(task_id)
        if task is not None:
            return task
        if json_fallback_read_enabled():
            logger.warning(
                "studio_task_postgres_read_miss_json_fallback",
                extra={"user_id": user_id, "task_id": task_id},
            )
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "studio_task_postgres_read_failed_json_fallback",
            extra={"user_id": user_id, "task_id": task_id, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_studio_tasks_for_project(
    user_id: str | None,
    project_id: str,
    json_loader,
) -> list[StudioTask]:
    """Read project tasks from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not studio_task_read_enabled():
        return json_loader()

    try:
        tasks = build_studio_task_read_repository(user_id).list_for_project(project_id)
        if tasks or not json_fallback_read_enabled():
            return tasks
        logger.warning(
            "studio_task_postgres_project_empty_json_fallback",
            extra={"user_id": user_id, "project_id": project_id},
        )
        return json_loader()
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "studio_task_postgres_project_read_failed_json_fallback",
            extra={"user_id": user_id, "project_id": project_id, "error": exc.__class__.__name__},
        )
        return json_loader()
