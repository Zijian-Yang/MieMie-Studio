"""create audio studio tables

Revision ID: 20260617_0009
Revises: 20260607_0008
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260617_0009"
down_revision = "20260607_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audio_studio_tasks",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("voice", sa.Text(), nullable=True),
        sa.Column("format", sa.Text(), nullable=True),
        sa.Column("result_audio_url", sa.Text(), nullable=True),
        sa.Column("result_voice_id", sa.Text(), nullable=True),
        sa.Column("audio_duration", sa.Float(), nullable=True),
        sa.Column("saved_to_library", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column(
            "markers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "raw_task_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_audio_studio_tasks_user_project_updated",
        "audio_studio_tasks",
        ["user_id", "project_id", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_audio_studio_tasks_user_status_updated",
        "audio_studio_tasks",
        ["user_id", "status", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_audio_studio_tasks_user_result_voice",
        "audio_studio_tasks",
        ["user_id", "result_voice_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "voice_profiles",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("voice_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("target_model", sa.Text(), nullable=True),
        sa.Column("prefix", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("preview_audio_url", sa.Text(), nullable=True),
        sa.Column("audio_url", sa.Text(), nullable=True),
        sa.Column(
            "raw_profile_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_voice_profiles_user_project_updated",
        "voice_profiles",
        ["user_id", "project_id", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_voice_profiles_user_voice_id",
        "voice_profiles",
        ["user_id", "voice_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_voice_profiles_user_status_updated",
        "voice_profiles",
        ["user_id", "status", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_voice_profiles_user_status_updated", table_name="voice_profiles")
    op.drop_index("idx_voice_profiles_user_voice_id", table_name="voice_profiles")
    op.drop_index("idx_voice_profiles_user_project_updated", table_name="voice_profiles")
    op.drop_table("voice_profiles")
    op.drop_index(
        "idx_audio_studio_tasks_user_result_voice",
        table_name="audio_studio_tasks",
    )
    op.drop_index(
        "idx_audio_studio_tasks_user_status_updated",
        table_name="audio_studio_tasks",
    )
    op.drop_index(
        "idx_audio_studio_tasks_user_project_updated",
        table_name="audio_studio_tasks",
    )
    op.drop_table("audio_studio_tasks")
