"""create video_studio_tasks

Revision ID: 20260607_0001
Revises:
Create Date: 2026-06-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260607_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_studio_tasks",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("task_kind", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("key_profile", sa.Text(), nullable=True),
        sa.Column("model_id", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("submit_state", sa.Text(), nullable=False, server_default="idle"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("group_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column(
            "input_assets",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "normalized_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("provider_payload_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provider_result_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "task_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "request_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "video_urls",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("selected_video_url", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("submit_attempt_id", sa.Text(), nullable=True),
        sa.Column("submit_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "raw_task_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_video_studio_tasks_user_project_updated",
        "video_studio_tasks",
        ["user_id", "project_id", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_video_studio_tasks_user_status_updated",
        "video_studio_tasks",
        ["user_id", "status", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_video_studio_tasks_submit_attempt",
        "video_studio_tasks",
        ["submit_attempt_id"],
        postgresql_where=sa.text("submit_attempt_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_video_studio_tasks_submit_attempt", table_name="video_studio_tasks")
    op.drop_index("idx_video_studio_tasks_user_status_updated", table_name="video_studio_tasks")
    op.drop_index("idx_video_studio_tasks_user_project_updated", table_name="video_studio_tasks")
    op.drop_table("video_studio_tasks")
