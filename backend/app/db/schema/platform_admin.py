"""Platform administrator settings and audit table definitions."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.schema import metadata


platform_settings = Table(
    "platform_settings",
    metadata,
    Column("id", Text, primary_key=True),
    Column("registration_enabled", Boolean, nullable=False, server_default=text("false")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("updated_by", Text, ForeignKey("users.id"), nullable=True),
)


admin_audit_logs = Table(
    "admin_audit_logs",
    metadata,
    Column("id", Text, primary_key=True),
    Column("actor_user_id", Text, ForeignKey("users.id"), nullable=False),
    Column("action", Text, nullable=False),
    Column("target_type", Text, nullable=False),
    Column("target_id", Text, nullable=True),
    Column("request_id", Text, nullable=True),
    Column("result", Text, nullable=False),
    Column("changes", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

Index(
    "idx_admin_audit_actor_created",
    admin_audit_logs.c.actor_user_id,
    admin_audit_logs.c.created_at.desc(),
)
Index(
    "idx_admin_audit_action_created",
    admin_audit_logs.c.action,
    admin_audit_logs.c.created_at.desc(),
)
Index(
    "idx_admin_audit_target_created",
    admin_audit_logs.c.target_type,
    admin_audit_logs.c.target_id,
    admin_audit_logs.c.created_at.desc(),
)
