"""Repositories and row mapping for session migration."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.db.schema.sessions import sessions
from app.repositories.base import RepositoryWriteError
from app.services.session_store import SessionRecord


SESSION_TTL = timedelta(days=7)


def token_sha256(token: str) -> str:
    """Return a stable one-way token hash for database storage and reconciliation."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_token_hash(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def _parse_datetime(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def session_to_row(token: str, record: SessionRecord, *, now: datetime | None = None) -> dict[str, Any]:
    """Convert a session token and file/Redis record into safe PostgreSQL columns."""

    created_at = _parse_datetime(record.created_at)
    if created_at is None:
        created_at = now or datetime.now(timezone.utc)
    snapshot = record.to_dict()
    snapshot["created_at"] = created_at.isoformat()
    return {
        "token_hash": token_sha256(token),
        "user_id": record.user_id,
        "raw_session_snapshot": snapshot,
        "created_at": created_at,
        "last_seen_at": created_at,
        "expires_at": created_at + SESSION_TTL,
        "deleted_at": None,
    }


def row_to_session_record(row: Mapping[str, Any]) -> SessionRecord:
    """Restore a session record from a PostgreSQL row."""

    snapshot = row.get("raw_session_snapshot")
    if isinstance(snapshot, dict):
        record = SessionRecord.from_raw(snapshot)
        if record:
            return record
    created_at = row["created_at"]
    return SessionRecord(
        user_id=row["user_id"],
        created_at=created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
    )


class PostgresSessionRepository:
    """PostgreSQL-backed session repository boundary for the migration path."""

    def __init__(self, engine):
        self._engine = engine

    def save(self, token: str, record: SessionRecord) -> None:
        row = session_to_row(token, record)
        statement = insert(sessions).values(**row)
        update_values = {
            key: statement.excluded[key]
            for key in row
            if key != "token_hash"
        }
        statement = statement.on_conflict_do_update(
            index_elements=[sessions.c.token_hash],
            set_=update_values,
        )
        try:
            with self._engine.begin() as conn:
                conn.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(f"Failed to save session for user {record.user_id}: {exc}") from exc

    def get(self, token: str) -> SessionRecord | None:
        statement = select(sessions).where(
            sessions.c.token_hash == token_sha256(token),
            sessions.c.deleted_at.is_(None),
            sessions.c.expires_at > datetime.now(timezone.utc),
        )
        with self._engine.connect() as conn:
            row = conn.execute(statement).mappings().first()
        return row_to_session_record(row) if row else None

    def list_all(self) -> dict[str, SessionRecord]:
        statement = select(sessions).where(
            sessions.c.deleted_at.is_(None),
            sessions.c.expires_at > datetime.now(timezone.utc),
        )
        with self._engine.connect() as conn:
            rows = conn.execute(statement).mappings().all()
        return {
            row["token_hash"]: row_to_session_record(row)
            for row in rows
        }

    def delete(self, token: str) -> None:
        statement = (
            update(sessions)
            .where(sessions.c.token_hash == token_sha256(token), sessions.c.deleted_at.is_(None))
            .values(deleted_at=datetime.now(timezone.utc))
        )
        try:
            with self._engine.begin() as conn:
                conn.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(f"Failed to delete session: {exc}") from exc

    def delete_user_sessions(self, user_id: str) -> int:
        statement = (
            update(sessions)
            .where(sessions.c.user_id == user_id, sessions.c.deleted_at.is_(None))
            .values(deleted_at=datetime.now(timezone.utc))
        )
        try:
            with self._engine.begin() as conn:
                result = conn.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(f"Failed to delete sessions for user {user_id}: {exc}") from exc
        return int(result.rowcount or 0)
