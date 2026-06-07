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


def user_config_read_enabled() -> bool:
    """Return true when user/config reads should prefer PostgreSQL."""

    if not database_enabled():
        return False

    read_mode = os.getenv("MIEMIE_DATABASE_READ_MODE", "file").strip().lower()
    read_domains = _env_csv("MIEMIE_DATABASE_READ_DOMAINS")
    return read_mode == "postgres" or DOMAIN in read_domains or user_config_primary_write_enabled()


def user_config_primary_write_enabled() -> bool:
    """Return true when user/config writes should use PostgreSQL primary."""

    if not database_enabled():
        return False

    write_mode = os.getenv("MIEMIE_DATABASE_WRITE_MODE", "file").strip().lower()
    primary_domains = _env_csv("MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS")
    return write_mode in {"postgres", "postgres_primary", "primary"} or DOMAIN in primary_domains


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


def build_user_shadow_repository() -> PostgresUserRepository:
    return PostgresUserRepository(_runtime_engine())


def build_user_config_shadow_repository() -> PostgresUserConfigRepository:
    return PostgresUserConfigRepository(_runtime_engine())


def build_user_read_repository() -> PostgresUserRepository:
    return PostgresUserRepository(_runtime_engine())


def build_user_config_read_repository() -> PostgresUserConfigRepository:
    return PostgresUserConfigRepository(_runtime_engine())


def build_user_primary_repository() -> PostgresUserRepository:
    return PostgresUserRepository(_runtime_engine())


def build_user_config_primary_repository() -> PostgresUserConfigRepository:
    return PostgresUserConfigRepository(_runtime_engine())


def _user_lookup_repository() -> PostgresUserRepository:
    if user_config_primary_write_enabled():
        return build_user_primary_repository()
    return build_user_read_repository()


def _config_lookup_repository() -> PostgresUserConfigRepository:
    if user_config_primary_write_enabled():
        return build_user_config_primary_repository()
    return build_user_config_read_repository()


def save_user_primary(user: User | None) -> bool:
    """Save a user to PostgreSQL as the primary store when enabled."""

    if user is None or not user_config_primary_write_enabled():
        return False

    build_user_primary_repository().save(user)
    return True


def save_config_primary(user_id: str | None, config: AppConfig) -> bool:
    """Save a per-user config to PostgreSQL as the primary store when enabled."""

    if not user_id or not user_config_primary_write_enabled():
        return False

    build_user_config_primary_repository().save(user_id, config)
    return True


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


def read_user(user_id: str | None, json_loader) -> User | None:
    """Read a user from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not user_config_read_enabled():
        return json_loader()

    try:
        user = _user_lookup_repository().get_by_id(user_id)
        if user is not None:
            return user
        if json_fallback_read_enabled():
            logger.warning("user_config_postgres_user_miss_json_fallback", extra={"user_id": user_id})
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "user_config_postgres_user_read_failed_json_fallback",
            extra={"user_id": user_id, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_user_by_username(username: str, json_loader) -> User | None:
    """Read a user by username from PostgreSQL when enabled, with optional JSON fallback."""

    if not username or not user_config_read_enabled():
        return json_loader()

    try:
        user = _user_lookup_repository().get_by_username(username)
        if user is not None:
            return user
        if json_fallback_read_enabled():
            logger.warning(
                "user_config_postgres_username_miss_json_fallback",
                extra={"username": username},
            )
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "user_config_postgres_username_read_failed_json_fallback",
            extra={"username": username, "error": exc.__class__.__name__},
        )
        return json_loader()


def read_config(user_id: str | None, json_loader) -> AppConfig:
    """Read a per-user config from PostgreSQL when enabled, with optional JSON fallback."""

    if not user_id or not user_config_read_enabled():
        return json_loader()

    try:
        config = _config_lookup_repository().get(user_id)
        if config is not None:
            return config
        if json_fallback_read_enabled():
            logger.warning("user_config_postgres_config_miss_json_fallback", extra={"user_id": user_id})
            return json_loader()
        return AppConfig()
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "user_config_postgres_config_read_failed_json_fallback",
            extra={"user_id": user_id, "error": exc.__class__.__name__},
        )
        return json_loader()
