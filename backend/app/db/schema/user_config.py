"""User and per-user configuration table definitions."""

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.schema import metadata


users = Table(
    "users",
    metadata,
    Column("id", Text, primary_key=True),
    Column("username", Text, nullable=False),
    Column("password_hash", Text, nullable=False),
    Column("display_name", Text, nullable=True),
    Column("role", Text, nullable=False, server_default=text("'member'")),
    Column("status", Text, nullable=False, server_default=text("'active'")),
    Column("must_change_password", Boolean, nullable=False, server_default=text("false")),
    Column("raw_user_snapshot", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("last_login", DateTime(timezone=True), nullable=True),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("role IN ('admin', 'member')", name="ck_users_role"),
    CheckConstraint("status IN ('active', 'disabled')", name="ck_users_status"),
)

Index(
    "idx_users_username_active_unique",
    users.c.username,
    unique=True,
    postgresql_where=users.c.deleted_at.is_(None),
)
Index(
    "idx_users_updated",
    users.c.updated_at.desc(),
    postgresql_where=users.c.deleted_at.is_(None),
)
Index(
    "idx_users_role_status_updated",
    users.c.role,
    users.c.status,
    users.c.updated_at.desc(),
    postgresql_where=users.c.deleted_at.is_(None),
)


user_configs = Table(
    "user_configs",
    metadata,
    Column("user_id", Text, ForeignKey("users.id"), primary_key=True),
    Column("raw_config_snapshot", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("api_region", Text, nullable=False),
    Column("has_dashscope_key", Boolean, nullable=False, server_default=text("false")),
    Column("has_oss_config", Boolean, nullable=False, server_default=text("false")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

Index(
    "idx_user_configs_updated",
    user_configs.c.updated_at.desc(),
    postgresql_where=user_configs.c.deleted_at.is_(None),
)
Index(
    "idx_user_configs_api_region",
    user_configs.c.api_region,
    postgresql_where=user_configs.c.deleted_at.is_(None),
)
