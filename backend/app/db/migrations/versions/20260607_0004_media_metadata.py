"""create media metadata tables

Revision ID: 20260607_0004
Revises: 20260607_0003
Create Date: 2026-06-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260607_0004"
down_revision = "20260607_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("asset_kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("fps", sa.Float(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("sample_rate", sa.Integer(), nullable=True),
        sa.Column("channels", sa.Integer(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("task_id", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("prompt_used", sa.Text(), nullable=True),
        sa.Column(
            "raw_media_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_media_assets_user_project_kind_updated",
        "media_assets",
        ["user_id", "project_id", "asset_kind", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_media_assets_user_url",
        "media_assets",
        ["user_id", "url"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_media_assets_task_id",
        "media_assets",
        ["task_id"],
        postgresql_where=sa.text("task_id IS NOT NULL"),
    )

    op.create_table(
        "text_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "raw_text_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_text_items_user_project_updated",
        "text_items",
        ["user_id", "project_id", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_text_items_user_category_updated",
        "text_items",
        ["user_id", "category", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_text_items_user_category_updated", table_name="text_items")
    op.drop_index("idx_text_items_user_project_updated", table_name="text_items")
    op.drop_table("text_items")
    op.drop_index("idx_media_assets_task_id", table_name="media_assets")
    op.drop_index("idx_media_assets_user_url", table_name="media_assets")
    op.drop_index("idx_media_assets_user_project_kind_updated", table_name="media_assets")
    op.drop_table("media_assets")
