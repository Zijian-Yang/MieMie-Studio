"""PostgreSQL connection and health helpers.

The migration starts with JSON as the primary data source, so this module is
deliberately lazy: it reads environment variables at call time and only imports
SQLAlchemy when database health is explicitly enabled.
"""

from __future__ import annotations

import os
from urllib.parse import SplitResult, urlsplit, urlunsplit


TRUE_VALUES = {"1", "true", "yes", "on"}


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


def database_health(timeout_seconds: float = 0.5) -> dict:
    """Return configured/ok/error database status without leaking credentials."""
    if not database_enabled():
        return {"configured": False, "ok": None}

    url = _database_url()
    if not url:
        return {"configured": False, "ok": False, "error": "MissingDatabaseUrl"}

    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.pool import NullPool

        connect_timeout = max(1, int(timeout_seconds))
        engine = create_engine(
            url,
            connect_args={"connect_timeout": connect_timeout},
            poolclass=NullPool,
        )
        try:
            with engine.connect() as connection:
                connection.execute(text("select 1"))
        finally:
            engine.dispose()
        return {"configured": True, "ok": True}
    except Exception as exc:
        return {"configured": True, "ok": False, "error": exc.__class__.__name__}
