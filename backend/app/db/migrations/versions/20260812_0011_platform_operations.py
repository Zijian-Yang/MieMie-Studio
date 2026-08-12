"""add platform operations schema

Revision ID: 20260812_0011
Revises: 20260812_0010
Create Date: 2026-08-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260812_0011"
down_revision = "20260812_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    settings_columns = (
        sa.Column("backup_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("backup_schedule", sa.Text(), nullable=False, server_default=sa.text("'03:00'")),
        sa.Column("backup_retention_days", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("backup_min_keep", sa.Integer(), nullable=False, server_default=sa.text("7")),
        sa.Column("backup_local_subdirectory", sa.Text(), nullable=False, server_default=sa.text("'postgres'")),
        sa.Column("backup_oss_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("backup_oss_endpoint", sa.Text(), nullable=True),
        sa.Column("backup_oss_bucket_name", sa.Text(), nullable=True),
        sa.Column("backup_oss_prefix", sa.Text(), nullable=False, server_default=sa.text("'miemie/backups'")),
        sa.Column("backup_oss_access_key_id_encrypted", sa.Text(), nullable=True),
        sa.Column("backup_oss_access_key_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("webhook_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("webhook_url_encrypted", sa.Text(), nullable=True),
        sa.Column("webhook_timeout_seconds", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("webhook_retry_count", sa.Integer(), nullable=False, server_default=sa.text("2")),
        sa.Column("webhook_alert_on_warning", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    for column in settings_columns:
        op.add_column("platform_settings", column)

    op.create_table(
        "operation_runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("operation_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("trigger_source", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Text(), nullable=True),
        sa.Column("local_status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("oss_status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("local_path_relative", sa.Text(), nullable=True),
        sa.Column("oss_object_key", sa.Text(), nullable=True),
        sa.Column("oss_etag", sa.Text(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_category", sa.Text(), nullable=True),
        sa.Column("artifact_relative_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "operation_type IN ('backup', 'oss_test', 'webhook_test', 'restore_rehearsal')",
            name="ck_operation_runs_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_operation_runs_status",
        ),
        sa.CheckConstraint(
            "trigger_source IN ('manual', 'scheduled', 'cli')",
            name="ck_operation_runs_trigger",
        ),
        sa.CheckConstraint(
            "local_status IN ('pending', 'succeeded', 'failed', 'skipped')",
            name="ck_operation_runs_local_status",
        ),
        sa.CheckConstraint(
            "oss_status IN ('pending', 'succeeded', 'failed', 'skipped')",
            name="ck_operation_runs_oss_status",
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_operation_runs_idempotency_unique",
        "operation_runs",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "idx_operation_runs_type_created",
        "operation_runs",
        ["operation_type", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_operation_runs_status_created",
        "operation_runs",
        ["status", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_operation_runs_status_created", table_name="operation_runs")
    op.drop_index("idx_operation_runs_type_created", table_name="operation_runs")
    op.drop_index("idx_operation_runs_idempotency_unique", table_name="operation_runs")
    op.drop_table("operation_runs")
    for name in (
        "webhook_alert_on_warning",
        "webhook_retry_count",
        "webhook_timeout_seconds",
        "webhook_url_encrypted",
        "webhook_enabled",
        "backup_oss_access_key_secret_encrypted",
        "backup_oss_access_key_id_encrypted",
        "backup_oss_prefix",
        "backup_oss_bucket_name",
        "backup_oss_endpoint",
        "backup_oss_enabled",
        "backup_local_subdirectory",
        "backup_min_keep",
        "backup_retention_days",
        "backup_schedule",
        "backup_enabled",
    ):
        op.drop_column("platform_settings", name)
