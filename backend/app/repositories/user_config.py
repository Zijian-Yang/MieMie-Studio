"""Repositories and row mapping for users and per-user configuration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.config import AppConfig
from app.db.schema.user_config import user_configs, users
from app.models.user import User
from app.repositories.base import RepositoryWriteError


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    raise TypeError(f"Unsupported datetime value: {value!r}")


def user_to_row(user: User) -> dict[str, Any]:
    """Convert the JSON-backed User model into indexed PostgreSQL columns."""

    created_at = _parse_datetime(user.created_at) or datetime.now(timezone.utc)
    last_login = _parse_datetime(user.last_login)
    updated_at = last_login or created_at
    return {
        "id": user.id,
        "username": user.username,
        "password_hash": user.password,
        "display_name": user.display_name,
        "raw_user_snapshot": user.model_dump(mode="json"),
        "created_at": created_at,
        "updated_at": updated_at,
        "last_login": last_login,
        "deleted_at": None,
    }


def row_to_user(row: Mapping[str, Any]) -> User:
    """Restore a User model from a PostgreSQL row."""

    snapshot = row.get("raw_user_snapshot")
    if snapshot:
        return User(**snapshot)
    created_at = row["created_at"]
    last_login = row.get("last_login")
    return User(
        id=row["id"],
        username=row["username"],
        password=row["password_hash"],
        display_name=row.get("display_name"),
        created_at=created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        last_login=last_login.isoformat() if isinstance(last_login, datetime) else last_login,
    )


def safe_config_indexes(config: AppConfig) -> dict[str, Any]:
    """Return queryable config flags without exposing secret values."""

    oss = config.oss
    return {
        "api_region": config.api_region,
        "has_dashscope_key": any(
            [
                bool(config.dashscope_api_key),
                bool(config.test_api_key),
                bool(config.production_api_key),
            ]
        ),
        "has_oss_config": bool(
            oss.enabled
            and oss.access_key_id
            and oss.access_key_secret
            and oss.bucket_name
        ),
    }


def config_to_row(user_id: str, config: AppConfig) -> dict[str, Any]:
    """Convert AppConfig into a DB row plus safe searchable indexes."""

    now = datetime.now(timezone.utc)
    indexes = safe_config_indexes(config)
    return {
        "user_id": user_id,
        "raw_config_snapshot": config.model_dump(mode="json"),
        "api_region": indexes["api_region"],
        "has_dashscope_key": indexes["has_dashscope_key"],
        "has_oss_config": indexes["has_oss_config"],
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }


def row_to_config(row: Mapping[str, Any]) -> AppConfig:
    """Restore AppConfig from a PostgreSQL row."""

    snapshot = row.get("raw_config_snapshot")
    if snapshot:
        return AppConfig(**snapshot)
    return AppConfig(api_region=row.get("api_region") or "beijing")


class PostgresUserRepository:
    """PostgreSQL-backed user repository boundary for the migration path."""

    def __init__(self, engine):
        self._engine = engine

    def save(self, user: User) -> None:
        row = user_to_row(user)
        statement = insert(users).values(**row)
        update_values = {
            key: statement.excluded[key]
            for key in row
            if key != "id"
        }
        statement = statement.on_conflict_do_update(
            index_elements=[users.c.id],
            set_=update_values,
        )
        try:
            with self._engine.begin() as conn:
                conn.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(f"Failed to save user {user.id}: {exc}") from exc

    def get_by_id(self, user_id: str) -> User | None:
        statement = select(users).where(users.c.id == user_id, users.c.deleted_at.is_(None))
        with self._engine.connect() as conn:
            row = conn.execute(statement).mappings().first()
        return row_to_user(row) if row else None

    def get_by_username(self, username: str) -> User | None:
        statement = select(users).where(users.c.username == username, users.c.deleted_at.is_(None))
        with self._engine.connect() as conn:
            row = conn.execute(statement).mappings().first()
        return row_to_user(row) if row else None

    def mark_deleted(self, user_id: str) -> None:
        statement = (
            update(users)
            .where(users.c.id == user_id, users.c.deleted_at.is_(None))
            .values(deleted_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
        )
        try:
            with self._engine.begin() as conn:
                conn.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(f"Failed to delete user {user_id}: {exc}") from exc


class PostgresUserConfigRepository:
    """PostgreSQL-backed per-user AppConfig repository boundary."""

    def __init__(self, engine):
        self._engine = engine

    def save(self, user_id: str, config: AppConfig) -> None:
        row = config_to_row(user_id, config)
        statement = insert(user_configs).values(**row)
        update_values = {
            key: statement.excluded[key]
            for key in row
            if key not in {"user_id", "created_at"}
        }
        statement = statement.on_conflict_do_update(
            index_elements=[user_configs.c.user_id],
            set_=update_values,
        )
        try:
            with self._engine.begin() as conn:
                conn.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(f"Failed to save config for user {user_id}: {exc}") from exc

    def get(self, user_id: str) -> AppConfig | None:
        statement = select(user_configs).where(
            user_configs.c.user_id == user_id,
            user_configs.c.deleted_at.is_(None),
        )
        with self._engine.connect() as conn:
            row = conn.execute(statement).mappings().first()
        return row_to_config(row) if row else None

    def mark_deleted(self, user_id: str) -> None:
        statement = (
            update(user_configs)
            .where(user_configs.c.user_id == user_id, user_configs.c.deleted_at.is_(None))
            .values(deleted_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
        )
        try:
            with self._engine.begin() as conn:
                conn.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(f"Failed to delete config for user {user_id}: {exc}") from exc
