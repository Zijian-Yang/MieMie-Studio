"""Media library table definitions."""

from sqlalchemy import Column, DateTime, Float, Index, Integer, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.schema import metadata


media_assets = Table(
    "media_assets",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("project_id", Text, nullable=False),
    Column("asset_kind", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=True),
    Column("url", Text, nullable=False),
    Column("file_type", Text, nullable=True),
    Column("file_size", Integer, nullable=False, server_default="0"),
    Column("duration", Float, nullable=True),
    Column("width", Integer, nullable=True),
    Column("height", Integer, nullable=True),
    Column("fps", Float, nullable=True),
    Column("thumbnail_url", Text, nullable=True),
    Column("sample_rate", Integer, nullable=True),
    Column("channels", Integer, nullable=True),
    Column("source", Text, nullable=True),
    Column("task_id", Text, nullable=True),
    Column("tags", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("prompt_used", Text, nullable=True),
    Column("raw_media_snapshot", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

Index(
    "idx_media_assets_user_project_kind_updated",
    media_assets.c.user_id,
    media_assets.c.project_id,
    media_assets.c.asset_kind,
    media_assets.c.updated_at.desc(),
    postgresql_where=media_assets.c.deleted_at.is_(None),
)
Index(
    "idx_media_assets_user_url",
    media_assets.c.user_id,
    media_assets.c.url,
    postgresql_where=media_assets.c.deleted_at.is_(None),
)
Index(
    "idx_media_assets_task_id",
    media_assets.c.task_id,
    postgresql_where=media_assets.c.task_id.is_not(None),
)


text_items = Table(
    "text_items",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("project_id", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("category", Text, nullable=False, server_default=""),
    Column("content", Text, nullable=False),
    Column("version_count", Integer, nullable=False, server_default="0"),
    Column("raw_text_snapshot", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

Index(
    "idx_text_items_user_project_updated",
    text_items.c.user_id,
    text_items.c.project_id,
    text_items.c.updated_at.desc(),
    postgresql_where=text_items.c.deleted_at.is_(None),
)
Index(
    "idx_text_items_user_category_updated",
    text_items.c.user_id,
    text_items.c.category,
    text_items.c.updated_at.desc(),
    postgresql_where=text_items.c.deleted_at.is_(None),
)
