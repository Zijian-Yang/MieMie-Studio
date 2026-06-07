"""Runtime feature flags for project PostgreSQL shadow writes."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from sqlalchemy.pool import NullPool

from app.db.engine import TRUE_VALUES, create_database_engine, database_enabled
from app.models.project import Project
from app.repositories.projects import PostgresProjectRepository


logger = logging.getLogger(__name__)

DOMAIN = "projects"


def _env_csv(name: str) -> set[str]:
    return {
        item.strip()
        for item in os.getenv(name, "").split(",")
        if item.strip()
    }


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def project_dual_write_enabled() -> bool:
    """Return true when project shadow writes are explicitly enabled."""

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


def build_project_shadow_repository(user_id: str) -> PostgresProjectRepository:
    return PostgresProjectRepository(_runtime_engine(), user_id)


def shadow_save_project(user_id: str | None, project: Project) -> None:
    """Shadow-save a project to PostgreSQL when dual-write is enabled."""

    if not user_id or not project_dual_write_enabled():
        return

    try:
        build_project_shadow_repository(user_id).save(project)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "project_runtime_shadow_save_failed",
            extra={"user_id": user_id, "project_id": project.id, "error": exc.__class__.__name__},
        )


def shadow_mark_project_deleted(user_id: str | None, project_id: str) -> None:
    """Shadow-mark a project deleted in PostgreSQL when dual-write is enabled."""

    if not user_id or not project_dual_write_enabled():
        return

    try:
        build_project_shadow_repository(user_id).mark_deleted(project_id)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "project_runtime_shadow_delete_failed",
            extra={"user_id": user_id, "project_id": project_id, "error": exc.__class__.__name__},
        )
