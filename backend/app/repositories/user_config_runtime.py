"""Runtime feature flags for user/config PostgreSQL shadow writes."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from sqlalchemy.pool import NullPool

from app.config import AppConfig
from app.db.engine import TRUE_VALUES, create_database_engine, database_enabled
from app.models.user import User
from app.repositories.user_config import PostgresUserConfigRepository, PostgresUserRepository


logger = logging.getLogger(__name__)

DOMAIN = "user_config"


def _env_csv(name: str) -> set[str]:
    return {
        item.strip()
        for item in os.getenv(name, "").split(",")
        if item.strip()
    }


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def user_config_dual_write_enabled() -> bool:
    """Return true when user/config shadow writes are explicitly enabled."""

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


def build_user_shadow_repository() -> PostgresUserRepository:
    return PostgresUserRepository(_runtime_engine())


def build_user_config_shadow_repository() -> PostgresUserConfigRepository:
    return PostgresUserConfigRepository(_runtime_engine())


def shadow_save_user(user: User | None) -> None:
    """Shadow-save a user to PostgreSQL when dual-write is enabled."""

    if user is None or not user_config_dual_write_enabled():
        return

    try:
        build_user_shadow_repository().save(user)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "user_config_shadow_save_user_failed",
            extra={"user_id": user.id, "error": exc.__class__.__name__},
        )


def shadow_save_config(user_id: str | None, config: AppConfig) -> None:
    """Shadow-save a per-user config to PostgreSQL when dual-write is enabled."""

    if not user_id or not user_config_dual_write_enabled():
        return

    try:
        build_user_config_shadow_repository().save(user_id, config)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "user_config_shadow_save_config_failed",
            extra={"user_id": user_id, "error": exc.__class__.__name__},
        )
