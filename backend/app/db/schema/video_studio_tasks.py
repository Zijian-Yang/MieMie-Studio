"""Video studio task table definition.

This first PostgreSQL domain is intentionally shaped as a task index plus an
escape-hatch JSONB snapshot. The indexed columns support list/status paths while
`raw_task_snapshot` preserves the full current Pydantic model during shadow and
reconciliation phases.
"""

from sqlalchemy import Column, DateTime, Index, Integer, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.schema import metadata


video_studio_tasks = Table(
    "video_studio_tasks",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("project_id", Text, nullable=False),
    Column("task_kind", Text, nullable=False),
    Column("task_type", Text, nullable=False),
    Column("provider", Text, nullable=False),
    Column("key_profile", Text, nullable=True),
    Column("model_id", Text, nullable=True),
    Column("model", Text, nullable=True),
    Column("name", Text, nullable=True),
    Column("status", Text, nullable=False),
    Column("submit_state", Text, nullable=False, server_default="idle"),
    Column("progress", Integer, nullable=False, server_default="0"),
    Column("group_count", Integer, nullable=False, server_default="1"),
    Column("prompt", Text, nullable=True),
    Column("negative_prompt", Text, nullable=True),
    Column("input_assets", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("normalized_params", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("provider_payload_snapshot", JSONB, nullable=True),
    Column("provider_result_meta", JSONB, nullable=True),
    Column("task_ids", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("request_ids", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("video_urls", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("selected_video_url", Text, nullable=True),
    Column("thumbnail_url", Text, nullable=True),
    Column("error_message", Text, nullable=True),
    Column("submit_attempt_id", Text, nullable=True),
    Column("submit_started_at", DateTime(timezone=True), nullable=True),
    Column("raw_task_snapshot", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

Index(
    "idx_video_studio_tasks_user_project_updated",
    video_studio_tasks.c.user_id,
    video_studio_tasks.c.project_id,
    video_studio_tasks.c.updated_at.desc(),
    postgresql_where=video_studio_tasks.c.deleted_at.is_(None),
)
Index(
    "idx_video_studio_tasks_user_status_updated",
    video_studio_tasks.c.user_id,
    video_studio_tasks.c.status,
    video_studio_tasks.c.updated_at.desc(),
    postgresql_where=video_studio_tasks.c.deleted_at.is_(None),
)
Index(
    "idx_video_studio_tasks_submit_attempt",
    video_studio_tasks.c.submit_attempt_id,
    postgresql_where=video_studio_tasks.c.submit_attempt_id.is_not(None),
)
