"""PostgreSQL connection and health helpers.

The migration starts with JSON as the primary data source, so this module is
deliberately lazy: it reads environment variables at call time and only imports
SQLAlchemy when database health is explicitly enabled.
"""

from __future__ import annotations

import os
import threading
from urllib.parse import SplitResult, urlsplit, urlunsplit


TRUE_VALUES = {"1", "true", "yes", "on"}
_health_engine_lock = threading.Lock()
_health_engine = None
_health_engine_key: tuple[str, int] | None = None


def database_enabled() -> bool:
    """Return true when MIEMIE_DATABASE_ENABLED is true/1/yes/on."""
    return os.getenv("MIEMIE_DATABASE_ENABLED", "").strip().lower() in TRUE_VALUES


def _database_url() -> str:
    return os.getenv("MIEMIE_DATABASE_URL", "").strip()


def database_url_configured() -> bool:
    """Return true when MIEMIE_DATABASE_URL is non-empty."""
    return bool(_database_url())


def sanitized_database_url() -> str | None:
    """Return a password-redacted database URL for logs only."""
    raw_url = _database_url()
    if not raw_url:
        return None

    try:
        parts = urlsplit(raw_url)
    except ValueError:
        return "[invalid-url]"

    if not parts.netloc:
        return raw_url

    hostname = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    username = parts.username or ""
    if username:
        credentials = f"{username}:***@"
    else:
        credentials = ""
    netloc = f"{credentials}{hostname}{port}"
    return urlunsplit(
        SplitResult(
            scheme=parts.scheme,
            netloc=netloc,
            path=parts.path,
            query=parts.query,
            fragment=parts.fragment,
        )
    )


def _dispose_database_health_engine() -> None:
    global _health_engine, _health_engine_key

    if _health_engine is not None:
        _health_engine.dispose()
    _health_engine = None
    _health_engine_key = None


def clear_database_health_engine() -> None:
    """Dispose the cached health-check engine.

    Runtime processes normally restart when database flags change. Tests and
    maintenance tools can call this helper when they mutate environment state
    in-process.
    """

    with _health_engine_lock:
        _dispose_database_health_engine()


def _health_connect_args(url: str, connect_timeout: int) -> dict:
    parts = urlsplit(url)
    if parts.scheme.startswith("postgresql"):
        return {"connect_timeout": connect_timeout}
    return {}


def _health_pool_options(url: str) -> dict:
    parts = urlsplit(url)
    if not parts.scheme.startswith("postgresql"):
        return {}

    return {
        "pool_size": int(os.getenv("MIEMIE_DATABASE_HEALTH_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("MIEMIE_DATABASE_HEALTH_MAX_OVERFLOW", "10")),
        "pool_timeout": float(os.getenv("MIEMIE_DATABASE_HEALTH_POOL_TIMEOUT", "1")),
        "pool_pre_ping": True,
    }


def _database_health_engine(url: str, connect_timeout: int):
    global _health_engine, _health_engine_key

    cache_key = (url, connect_timeout)
    with _health_engine_lock:
        if _health_engine is not None and _health_engine_key == cache_key:
            return _health_engine

        _dispose_database_health_engine()

        from sqlalchemy import create_engine

        _health_engine = create_engine(
            url,
            connect_args=_health_connect_args(url, connect_timeout),
            **_health_pool_options(url),
        )
        _health_engine_key = cache_key
        return _health_engine


def database_health(timeout_seconds: float = 0.5) -> dict:
    """Return configured/ok/error database status without leaking credentials."""
    if not database_enabled():
        clear_database_health_engine()
        return {"configured": False, "ok": None}

    url = _database_url()
    if not url:
        clear_database_health_engine()
        return {"configured": False, "ok": False, "error": "MissingDatabaseUrl"}

    try:
        from sqlalchemy import text

        connect_timeout = max(1, int(timeout_seconds))
        engine = _database_health_engine(url, connect_timeout)
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        return {"configured": True, "ok": True}
    except Exception as exc:
        return {"configured": True, "ok": False, "error": exc.__class__.__name__}


def create_database_engine(**kwargs):
    """Create a SQLAlchemy engine from MIEMIE_DATABASE_URL for maintenance jobs."""
    url = _database_url()
    if not url:
        raise RuntimeError("MIEMIE_DATABASE_URL is required")

    from sqlalchemy import create_engine

    return create_engine(url, **kwargs)
