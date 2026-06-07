"""create project entity table

Revision ID: 20260607_0005
Revises: 20260607_0004
Create Date: 2026-06-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260607_0005"
down_revision = "20260607_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_entities",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("entity_kind", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("shot_id", sa.Text(), nullable=True),
        sa.Column("shot_number", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("selected_group_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "raw_entity_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", "entity_kind"),
    )
    op.create_index(
        "idx_project_entities_user_project_kind_updated",
        "project_entities",
        ["user_id", "project_id", "entity_kind", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_project_entities_user_kind_name",
        "project_entities",
        ["user_id", "entity_kind", "name"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_project_entities_user_project_kind_shot",
        "project_entities",
        ["user_id", "project_id", "entity_kind", "shot_id", "shot_number"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_project_entities_user_project_kind_shot", table_name="project_entities")
    op.drop_index("idx_project_entities_user_kind_name", table_name="project_entities")
    op.drop_index("idx_project_entities_user_project_kind_updated", table_name="project_entities")
    op.drop_table("project_entities")
