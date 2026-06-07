"""Runtime feature flags for project entity PostgreSQL shadow writes and reads."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Callable

from sqlalchemy.pool import NullPool

from app.db.engine import TRUE_VALUES, create_database_engine, database_enabled
from app.repositories.project_entities import PostgresProjectEntityRepository, ProjectEntity


logger = logging.getLogger(__name__)

DOMAIN = "project_entities"


def _env_csv(name: str) -> set[str]:
    return {
        item.strip()
        for item in os.getenv(name, "").split(",")
        if item.strip()
    }


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def project_entity_dual_write_enabled() -> bool:
    """Return true when project entity shadow writes are explicitly enabled."""

    if not database_enabled():
        return False

    write_mode = os.getenv("MIEMIE_DATABASE_WRITE_MODE", "file").strip().lower()
    dual_domains = _env_csv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS")
    return write_mode in {"dual", "dual_write"} or DOMAIN in dual_domains


def project_entity_read_enabled() -> bool:
    """Return true when project entity reads should prefer PostgreSQL."""

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


def build_project_entity_shadow_repository(user_id: str) -> PostgresProjectEntityRepository:
    return PostgresProjectEntityRepository(_runtime_engine(), user_id)


def build_project_entity_read_repository(user_id: str) -> PostgresProjectEntityRepository:
    return PostgresProjectEntityRepository(_runtime_engine(), user_id)


def shadow_save_project_entity(user_id: str | None, entity_kind: str, entity: ProjectEntity) -> None:
    """Shadow-save a project editing entity to PostgreSQL when dual-write is enabled."""

    if not user_id or not project_entity_dual_write_enabled():
        return

    try:
        build_project_entity_shadow_repository(user_id).save(entity_kind, entity)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "project_entity_shadow_save_failed",
            extra={
                "user_id": user_id,
                "entity_kind": entity_kind,
                "entity_id": entity.id,
                "error": exc.__class__.__name__,
            },
        )


def shadow_mark_project_entity_deleted(user_id: str | None, entity_kind: str, entity_id: str) -> None:
    """Shadow-mark a project editing entity deleted when dual-write is enabled."""

    if not user_id or not project_entity_dual_write_enabled():
        return

    try:
        build_project_entity_shadow_repository(user_id).mark_deleted(entity_kind, entity_id)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "project_entity_shadow_delete_failed",
            extra={
                "user_id": user_id,
                "entity_kind": entity_kind,
                "entity_id": entity_id,
                "error": exc.__class__.__name__,
            },
        )


def read_project_entity(
    user_id: str | None,
    entity_kind: str,
    entity_id: str,
    json_loader: Callable[[], ProjectEntity | None],
) -> ProjectEntity | None:
    """Read one project editing entity from PostgreSQL when enabled."""

    if not user_id or not project_entity_read_enabled():
        return json_loader()

    try:
        entity = build_project_entity_read_repository(user_id).get(entity_kind, entity_id)
        if entity is not None:
            return entity
        if json_fallback_read_enabled():
            logger.warning(
                "project_entity_postgres_read_miss_json_fallback",
                extra={"user_id": user_id, "entity_kind": entity_kind, "entity_id": entity_id},
            )
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "project_entity_postgres_read_failed_json_fallback",
            extra={
                "user_id": user_id,
                "entity_kind": entity_kind,
                "entity_id": entity_id,
                "error": exc.__class__.__name__,
            },
        )
        return json_loader()


def read_project_entities_for_project(
    user_id: str | None,
    entity_kind: str,
    project_id: str,
    json_loader: Callable[[], list[ProjectEntity]],
) -> list[ProjectEntity]:
    """Read project editing entities from PostgreSQL when enabled."""

    if not user_id or not project_entity_read_enabled():
        return json_loader()

    try:
        entities = build_project_entity_read_repository(user_id).list_for_project(entity_kind, project_id)
        if entities or not json_fallback_read_enabled():
            return entities
        logger.warning(
            "project_entity_postgres_project_empty_json_fallback",
            extra={"user_id": user_id, "entity_kind": entity_kind, "project_id": project_id},
        )
        return json_loader()
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "project_entity_postgres_project_read_failed_json_fallback",
            extra={
                "user_id": user_id,
                "entity_kind": entity_kind,
                "project_id": project_id,
                "error": exc.__class__.__name__,
            },
        )
        return json_loader()


def read_project_entity_from_project_list(
    user_id: str | None,
    entity_kind: str,
    project_id: str,
    predicate: Callable[[ProjectEntity], bool],
    json_loader: Callable[[], ProjectEntity | None],
) -> ProjectEntity | None:
    """Read one entity by filtering a PostgreSQL project list when enabled."""

    if not user_id or not project_entity_read_enabled():
        return json_loader()

    try:
        entities = build_project_entity_read_repository(user_id).list_for_project(entity_kind, project_id)
        entity = next((item for item in entities if predicate(item)), None)
        if entity is not None:
            return entity
        if json_fallback_read_enabled():
            logger.warning(
                "project_entity_postgres_project_lookup_miss_json_fallback",
                extra={"user_id": user_id, "entity_kind": entity_kind, "project_id": project_id},
            )
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "project_entity_postgres_project_lookup_failed_json_fallback",
            extra={
                "user_id": user_id,
                "entity_kind": entity_kind,
                "project_id": project_id,
                "error": exc.__class__.__name__,
            },
        )
        return json_loader()


def read_project_entity_from_kind_list(
    user_id: str | None,
    entity_kind: str,
    predicate: Callable[[ProjectEntity], bool],
    json_loader: Callable[[], ProjectEntity | None],
) -> ProjectEntity | None:
    """Read one entity by filtering a PostgreSQL kind list when enabled."""

    if not user_id or not project_entity_read_enabled():
        return json_loader()

    try:
        entities = build_project_entity_read_repository(user_id).list_all(entity_kind)
        entity = next((item for item in entities if predicate(item)), None)
        if entity is not None:
            return entity
        if json_fallback_read_enabled():
            logger.warning(
                "project_entity_postgres_kind_lookup_miss_json_fallback",
                extra={"user_id": user_id, "entity_kind": entity_kind},
            )
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "project_entity_postgres_kind_lookup_failed_json_fallback",
            extra={"user_id": user_id, "entity_kind": entity_kind, "error": exc.__class__.__name__},
        )
        return json_loader()
