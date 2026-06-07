"""Project editing entity table definitions."""

from sqlalchemy import Column, DateTime, Index, Integer, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.schema import metadata


project_entities = Table(
    "project_entities",
    metadata,
    Column("id", Text, primary_key=True),
    Column("entity_kind", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("project_id", Text, nullable=False),
    Column("name", Text, nullable=True),
    Column("shot_id", Text, nullable=True),
    Column("shot_number", Integer, nullable=True),
    Column("status", Text, nullable=True),
    Column("thumbnail_url", Text, nullable=True),
    Column("selected_group_index", Integer, nullable=False, server_default="0"),
    Column("raw_entity_snapshot", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

Index(
    "idx_project_entities_user_project_kind_updated",
    project_entities.c.user_id,
    project_entities.c.project_id,
    project_entities.c.entity_kind,
    project_entities.c.updated_at.desc(),
    postgresql_where=project_entities.c.deleted_at.is_(None),
)
Index(
    "idx_project_entities_user_kind_name",
    project_entities.c.user_id,
    project_entities.c.entity_kind,
    project_entities.c.name,
    postgresql_where=project_entities.c.deleted_at.is_(None),
)
Index(
    "idx_project_entities_user_project_kind_shot",
    project_entities.c.user_id,
    project_entities.c.project_id,
    project_entities.c.entity_kind,
    project_entities.c.shot_id,
    project_entities.c.shot_number,
    postgresql_where=project_entities.c.deleted_at.is_(None),
)
