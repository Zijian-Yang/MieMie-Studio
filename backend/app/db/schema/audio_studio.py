"""Audio studio table definitions."""

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.schema import metadata


audio_studio_tasks = Table(
    "audio_studio_tasks",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("project_id", Text, nullable=False),
    Column("task_type", Text, nullable=False),
    Column("name", Text, nullable=True),
    Column("status", Text, nullable=False),
    Column("voice", Text, nullable=True),
    Column("format", Text, nullable=True),
    Column("result_audio_url", Text, nullable=True),
    Column("result_voice_id", Text, nullable=True),
    Column("audio_duration", Float, nullable=True),
    Column("saved_to_library", Boolean, nullable=False, server_default="false"),
    Column("request_id", Text, nullable=True),
    Column("markers", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("error_message", Text, nullable=True),
    Column("raw_task_snapshot", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

voice_profiles = Table(
    "voice_profiles",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("project_id", Text, nullable=False),
    Column("voice_id", Text, nullable=False),
    Column("name", Text, nullable=True),
    Column("source", Text, nullable=False),
    Column("target_model", Text, nullable=True),
    Column("prefix", Text, nullable=True),
    Column("status", Text, nullable=False),
    Column("preview_audio_url", Text, nullable=True),
    Column("audio_url", Text, nullable=True),
    Column("raw_profile_snapshot", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

Index(
    "idx_audio_studio_tasks_user_project_updated",
    audio_studio_tasks.c.user_id,
    audio_studio_tasks.c.project_id,
    audio_studio_tasks.c.updated_at.desc(),
    postgresql_where=audio_studio_tasks.c.deleted_at.is_(None),
)
Index(
    "idx_audio_studio_tasks_user_status_updated",
    audio_studio_tasks.c.user_id,
    audio_studio_tasks.c.status,
    audio_studio_tasks.c.updated_at.desc(),
    postgresql_where=audio_studio_tasks.c.deleted_at.is_(None),
)
Index(
    "idx_audio_studio_tasks_user_result_voice",
    audio_studio_tasks.c.user_id,
    audio_studio_tasks.c.result_voice_id,
    postgresql_where=audio_studio_tasks.c.deleted_at.is_(None),
)

Index(
    "idx_voice_profiles_user_project_updated",
    voice_profiles.c.user_id,
    voice_profiles.c.project_id,
    voice_profiles.c.updated_at.desc(),
    postgresql_where=voice_profiles.c.deleted_at.is_(None),
)
Index(
    "idx_voice_profiles_user_voice_id",
    voice_profiles.c.user_id,
    voice_profiles.c.voice_id,
    postgresql_where=voice_profiles.c.deleted_at.is_(None),
)
Index(
    "idx_voice_profiles_user_status_updated",
    voice_profiles.c.user_id,
    voice_profiles.c.status,
    voice_profiles.c.updated_at.desc(),
    postgresql_where=voice_profiles.c.deleted_at.is_(None),
)
