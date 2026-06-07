"""Project table definition."""

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.schema import metadata


projects = Table(
    "projects",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=True),
    Column("has_script", Boolean, nullable=False, server_default="false"),
    Column("script_shot_count", Integer, nullable=False, server_default="0"),
    Column("character_count", Integer, nullable=False, server_default="0"),
    Column("scene_count", Integer, nullable=False, server_default="0"),
    Column("prop_count", Integer, nullable=False, server_default="0"),
    Column("style_count", Integer, nullable=False, server_default="0"),
    Column("llm_configs", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("raw_project_snapshot", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

Index(
    "idx_projects_user_updated",
    projects.c.user_id,
    projects.c.updated_at.desc(),
    postgresql_where=projects.c.deleted_at.is_(None),
)
Index(
    "idx_projects_user_name",
    projects.c.user_id,
    projects.c.name,
    postgresql_where=projects.c.deleted_at.is_(None),
)
