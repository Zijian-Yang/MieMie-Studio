"""Session table definition for PostgreSQL migration."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.schema import metadata


sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", Text, primary_key=True),
    Column("user_id", Text, ForeignKey("users.id"), nullable=False),
    Column("raw_session_snapshot", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

Index(
    "idx_sessions_user_active",
    sessions.c.user_id,
    sessions.c.last_seen_at.desc(),
    postgresql_where=sessions.c.deleted_at.is_(None),
)
Index(
    "idx_sessions_expires_active",
    sessions.c.expires_at,
    postgresql_where=sessions.c.deleted_at.is_(None),
)
