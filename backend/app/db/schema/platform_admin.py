"""Platform administrator settings and audit table definitions."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.schema import metadata


platform_settings = Table(
    "platform_settings",
    metadata,
    Column("id", Text, primary_key=True),
    Column("registration_enabled", Boolean, nullable=False, server_default=text("false")),
    Column("backup_enabled", Boolean, nullable=False, server_default=text("false")),
    Column("backup_schedule", Text, nullable=False, server_default=text("'03:00'")),
    Column("backup_retention_days", Integer, nullable=False, server_default=text("30")),
    Column("backup_min_keep", Integer, nullable=False, server_default=text("7")),
    Column("backup_local_subdirectory", Text, nullable=False, server_default=text("'postgres'")),
    Column("backup_oss_enabled", Boolean, nullable=False, server_default=text("false")),
    Column("backup_oss_endpoint", Text, nullable=True),
    Column("backup_oss_bucket_name", Text, nullable=True),
    Column("backup_oss_prefix", Text, nullable=False, server_default=text("'miemie/backups'")),
    Column("backup_oss_access_key_id_encrypted", Text, nullable=True),
    Column("backup_oss_access_key_secret_encrypted", Text, nullable=True),
    Column("webhook_enabled", Boolean, nullable=False, server_default=text("false")),
    Column("webhook_url_encrypted", Text, nullable=True),
    Column("webhook_timeout_seconds", Integer, nullable=False, server_default=text("10")),
    Column("webhook_retry_count", Integer, nullable=False, server_default=text("2")),
    Column("webhook_alert_on_warning", Boolean, nullable=False, server_default=text("false")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("updated_by", Text, ForeignKey("users.id"), nullable=True),
)


operation_runs = Table(
    "operation_runs",
    metadata,
    Column("id", Text, primary_key=True),
    Column("operation_type", Text, nullable=False),
    Column("status", Text, nullable=False, server_default=text("'queued'")),
    Column("trigger_source", Text, nullable=False),
    Column("idempotency_key", Text, nullable=True),
    Column("requested_by", Text, ForeignKey("users.id"), nullable=True),
    Column("local_status", Text, nullable=False, server_default=text("'pending'")),
    Column("oss_status", Text, nullable=False, server_default=text("'pending'")),
    Column("local_path_relative", Text, nullable=True),
    Column("oss_object_key", Text, nullable=True),
    Column("oss_etag", Text, nullable=True),
    Column("sha256", Text, nullable=True),
    Column("size_bytes", BigInteger, nullable=True),
    Column("summary", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("error_category", Text, nullable=True),
    Column("artifact_relative_path", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "operation_type IN ('backup', 'oss_test', 'webhook_test', 'restore_rehearsal')",
        name="ck_operation_runs_type",
    ),
    CheckConstraint(
        "status IN ('queued', 'running', 'succeeded', 'failed')",
        name="ck_operation_runs_status",
    ),
    CheckConstraint(
        "trigger_source IN ('manual', 'scheduled', 'cli')",
        name="ck_operation_runs_trigger",
    ),
    CheckConstraint(
        "local_status IN ('pending', 'succeeded', 'failed', 'skipped')",
        name="ck_operation_runs_local_status",
    ),
    CheckConstraint(
        "oss_status IN ('pending', 'succeeded', 'failed', 'skipped')",
        name="ck_operation_runs_oss_status",
    ),
)

Index(
    "idx_operation_runs_idempotency_unique",
    operation_runs.c.idempotency_key,
    unique=True,
    postgresql_where=operation_runs.c.idempotency_key.is_not(None),
)
Index(
    "idx_operation_runs_type_created",
    operation_runs.c.operation_type,
    operation_runs.c.created_at.desc(),
)
Index(
    "idx_operation_runs_status_created",
    operation_runs.c.status,
    operation_runs.c.created_at.desc(),
)


admin_audit_logs = Table(
    "admin_audit_logs",
    metadata,
    Column("id", Text, primary_key=True),
    Column("actor_user_id", Text, ForeignKey("users.id"), nullable=False),
    Column("action", Text, nullable=False),
    Column("target_type", Text, nullable=False),
    Column("target_id", Text, nullable=True),
    Column("request_id", Text, nullable=True),
    Column("result", Text, nullable=False),
    Column("changes", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

Index(
    "idx_admin_audit_actor_created",
    admin_audit_logs.c.actor_user_id,
    admin_audit_logs.c.created_at.desc(),
)
Index(
    "idx_admin_audit_action_created",
    admin_audit_logs.c.action,
    admin_audit_logs.c.created_at.desc(),
)
Index(
    "idx_admin_audit_target_created",
    admin_audit_logs.c.target_type,
    admin_audit_logs.c.target_id,
    admin_audit_logs.c.created_at.desc(),
)
