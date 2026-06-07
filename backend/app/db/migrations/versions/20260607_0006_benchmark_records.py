"""create benchmark records table

Revision ID: 20260607_0006
Revises: 20260607_0005
Create Date: 2026-06-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260607_0006"
down_revision = "20260607_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benchmark_records",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("benchmark_kind", sa.Text(), nullable=False),
        sa.Column("record_kind", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("dataset_id", sa.Text(), nullable=True),
        sa.Column("suite_id", sa.Text(), nullable=True),
        sa.Column("task_kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cell_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "raw_record_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", "benchmark_kind", "record_kind"),
    )
    op.create_index(
        "idx_benchmark_records_user_project_kind_updated",
        "benchmark_records",
        ["user_id", "project_id", "benchmark_kind", "record_kind", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_benchmark_records_user_suite_runs",
        "benchmark_records",
        ["user_id", "benchmark_kind", "suite_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_benchmark_records_user_dataset_suites",
        "benchmark_records",
        ["user_id", "benchmark_kind", "dataset_id", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_benchmark_records_user_dataset_suites", table_name="benchmark_records")
    op.drop_index("idx_benchmark_records_user_suite_runs", table_name="benchmark_records")
    op.drop_index("idx_benchmark_records_user_project_kind_updated", table_name="benchmark_records")
    op.drop_table("benchmark_records")
