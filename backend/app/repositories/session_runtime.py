"""Runtime feature flags for session PostgreSQL migration."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from sqlalchemy.pool import NullPool

from app.db.engine import TRUE_VALUES, create_database_engine, database_enabled
from app.repositories.sessions import PostgresSessionRepository
from app.services.session_store import SessionRecord


logger = logging.getLogger(__name__)

DOMAIN = "sessions"


def _env_csv(name: str) -> set[str]:
    return {
        item.strip()
        for item in os.getenv(name, "").split(",")
        if item.strip()
    }


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def session_dual_write_enabled() -> bool:
    """Return true when session shadow writes are explicitly enabled."""

    if not database_enabled():
        return False

    write_mode = os.getenv("MIEMIE_DATABASE_WRITE_MODE", "file").strip().lower()
    dual_domains = _env_csv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS")
    return write_mode in {"dual", "dual_write"} or DOMAIN in dual_domains


def session_read_enabled() -> bool:
    """Return true when session reads should prefer PostgreSQL."""

    if not database_enabled():
        return False

    read_mode = os.getenv("MIEMIE_DATABASE_READ_MODE", "file").strip().lower()
    read_domains = _env_csv("MIEMIE_DATABASE_READ_DOMAINS")
    return read_mode == "postgres" or DOMAIN in read_domains or session_primary_write_enabled()


def session_primary_write_enabled() -> bool:
    """Return true when session writes should use PostgreSQL primary."""

    if not database_enabled():
        return False

    write_mode = os.getenv("MIEMIE_DATABASE_WRITE_MODE", "file").strip().lower()
    primary_domains = _env_csv("MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS")
    return write_mode in {"postgres", "postgres_primary", "primary"} or DOMAIN in primary_domains


def json_fallback_read_enabled() -> bool:
    """Return true when PostgreSQL read miss/error should fallback to Redis/file."""

    return _env_true("MIEMIE_DATABASE_JSON_FALLBACK_READ")


def json_archive_writes_enabled() -> bool:
    """Return true when PostgreSQL primary writes should maintain session JSON mirrors."""

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


def build_session_shadow_repository() -> PostgresSessionRepository:
    return PostgresSessionRepository(_runtime_engine())


def build_session_read_repository() -> PostgresSessionRepository:
    return PostgresSessionRepository(_runtime_engine())


def build_session_primary_repository() -> PostgresSessionRepository:
    return PostgresSessionRepository(_runtime_engine())


def read_session(token: str, current_loader) -> dict | None:
    """Read a session from PostgreSQL when enabled, with optional Redis/file fallback."""

    if not token or not session_read_enabled():
        return current_loader()

    try:
        record = build_session_read_repository().get(token)
        if record is not None:
            return record.to_dict()
        if json_fallback_read_enabled():
            logger.warning("session_runtime_postgres_miss_current_fallback")
            return current_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "session_runtime_postgres_read_failed_current_fallback",
            extra={"error": exc.__class__.__name__},
        )
        return current_loader()


def save_session_primary(token: str, record: SessionRecord | None) -> bool:
    """Save a session to PostgreSQL as the primary store when enabled."""

    if not token or record is None or not session_primary_write_enabled():
        return False

    build_session_primary_repository().save(token, record)
    return True


def delete_session_primary(token: str) -> bool:
    """Delete a session from PostgreSQL primary store when enabled."""

    if not token or not session_primary_write_enabled():
        return False

    build_session_primary_repository().delete(token)
    return True


def delete_user_sessions_primary(user_id: str | None) -> bool:
    """Delete all sessions for one user from PostgreSQL primary store when enabled."""

    if not user_id or not session_primary_write_enabled():
        return False

    build_session_primary_repository().delete_user_sessions(user_id)
    return True


def shadow_save_session(token: str, record: SessionRecord | None) -> None:
    """Shadow-save a session to PostgreSQL when dual-write is enabled."""

    if not token or record is None or not session_dual_write_enabled():
        return

    try:
        build_session_shadow_repository().save(token, record)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "session_runtime_shadow_save_failed",
            extra={"user_id": record.user_id, "error": exc.__class__.__name__},
        )


def shadow_delete_session(token: str) -> None:
    """Shadow-delete a single session in PostgreSQL when dual-write is enabled."""

    if not token or not session_dual_write_enabled():
        return

    try:
        build_session_shadow_repository().delete(token)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "session_runtime_shadow_delete_failed",
            extra={"error": exc.__class__.__name__},
        )


def shadow_delete_user_sessions(user_id: str | None) -> None:
    """Shadow-delete all sessions for one user in PostgreSQL when dual-write is enabled."""

    if not user_id or not session_dual_write_enabled():
        return

    try:
        build_session_shadow_repository().delete_user_sessions(user_id)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "session_runtime_shadow_delete_user_failed",
            extra={"user_id": user_id, "error": exc.__class__.__name__},
        )
