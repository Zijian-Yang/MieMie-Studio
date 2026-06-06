"""Image studio task table definition."""

from sqlalchemy import Column, DateTime, Index, Integer, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.schema import metadata


studio_tasks = Table(
    "studio_tasks",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("project_id", Text, nullable=False),
    Column("task_kind", Text, nullable=False),
    Column("provider", Text, nullable=False),
    Column("model_id", Text, nullable=True),
    Column("model", Text, nullable=True),
    Column("name", Text, nullable=True),
    Column("status", Text, nullable=False),
    Column("group_count", Integer, nullable=False, server_default="1"),
    Column("image_count", Integer, nullable=False, server_default="0"),
    Column("selected_image_count", Integer, nullable=False, server_default="0"),
    Column("prompt", Text, nullable=True),
    Column("negative_prompt", Text, nullable=True),
    Column("input_assets", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("normalized_params", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("provider_payload_snapshot", JSONB, nullable=True),
    Column("provider_result_meta", JSONB, nullable=True),
    Column("task_ids", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("request_ids", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("images", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("warnings", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("error_message", Text, nullable=True),
    Column("last_task_id", Text, nullable=True),
    Column("last_request_id", Text, nullable=True),
    Column("raw_task_snapshot", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

Index(
    "idx_studio_tasks_user_project_updated",
    studio_tasks.c.user_id,
    studio_tasks.c.project_id,
    studio_tasks.c.updated_at.desc(),
    postgresql_where=studio_tasks.c.deleted_at.is_(None),
)
Index(
    "idx_studio_tasks_user_status_updated",
    studio_tasks.c.user_id,
    studio_tasks.c.status,
    studio_tasks.c.updated_at.desc(),
    postgresql_where=studio_tasks.c.deleted_at.is_(None),
)
