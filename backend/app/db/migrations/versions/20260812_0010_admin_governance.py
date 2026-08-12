"""add administrator governance schema

Revision ID: 20260812_0010
Revises: 20260617_0009
Create Date: 2026-08-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260812_0010"
down_revision = "20260617_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'member'")),
    )
    op.add_column(
        "users",
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
    )
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_check_constraint("ck_users_role", "users", "role IN ('admin', 'member')")
    op.create_check_constraint("ck_users_status", "users", "status IN ('active', 'disabled')")
    op.create_index(
        "idx_users_role_status_updated",
        "users",
        ["role", "status", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("registration_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "INSERT INTO platform_settings "
        "(id, registration_enabled, created_at, updated_at) "
        "VALUES ('platform', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column(
            "changes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_admin_audit_actor_created",
        "admin_audit_logs",
        ["actor_user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_admin_audit_action_created",
        "admin_audit_logs",
        ["action", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_admin_audit_target_created",
        "admin_audit_logs",
        ["target_type", "target_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_admin_audit_target_created", table_name="admin_audit_logs")
    op.drop_index("idx_admin_audit_action_created", table_name="admin_audit_logs")
    op.drop_index("idx_admin_audit_actor_created", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
    op.drop_table("platform_settings")
    op.drop_index("idx_users_role_status_updated", table_name="users")
    op.drop_constraint("ck_users_status", "users", type_="check")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "status")
    op.drop_column("users", "role")
