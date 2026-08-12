import io
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.schema import metadata
from app.db.schema.platform_admin import operation_runs, platform_settings


def test_platform_settings_contains_operational_policy_and_encrypted_secrets():
    expected = {
        "id",
        "registration_enabled",
        "backup_enabled",
        "backup_schedule",
        "backup_retention_days",
        "backup_min_keep",
        "backup_local_subdirectory",
        "backup_oss_enabled",
        "backup_oss_endpoint",
        "backup_oss_bucket_name",
        "backup_oss_prefix",
        "backup_oss_access_key_id_encrypted",
        "backup_oss_access_key_secret_encrypted",
        "webhook_enabled",
        "webhook_url_encrypted",
        "webhook_timeout_seconds",
        "webhook_retry_count",
        "webhook_alert_on_warning",
        "created_at",
        "updated_at",
        "updated_by",
    }
    assert set(platform_settings.c.keys()) == expected

    ddl = str(CreateTable(platform_settings).compile(dialect=postgresql.dialect()))
    assert "backup_enabled BOOLEAN DEFAULT false NOT NULL" in ddl
    assert "backup_schedule TEXT DEFAULT '03:00' NOT NULL" in ddl
    assert "backup_retention_days INTEGER DEFAULT 30 NOT NULL" in ddl
    assert "backup_min_keep INTEGER DEFAULT 7 NOT NULL" in ddl
    assert "backup_local_subdirectory TEXT DEFAULT 'postgres' NOT NULL" in ddl
    assert "webhook_timeout_seconds INTEGER DEFAULT 10 NOT NULL" in ddl
    assert "webhook_retry_count INTEGER DEFAULT 2 NOT NULL" in ddl
    assert "access_key_id TEXT" not in ddl
    assert "webhook_url TEXT" not in ddl


def test_operation_runs_schema_has_state_local_oss_and_idempotency_contracts():
    assert metadata.tables["operation_runs"] is operation_runs
    assert set(operation_runs.c.keys()) == {
        "id",
        "operation_type",
        "status",
        "trigger_source",
        "idempotency_key",
        "requested_by",
        "local_status",
        "oss_status",
        "local_path_relative",
        "oss_object_key",
        "oss_etag",
        "sha256",
        "size_bytes",
        "summary",
        "error_category",
        "artifact_relative_path",
        "created_at",
        "started_at",
        "finished_at",
        "updated_at",
    }
    assert operation_runs.c.id.primary_key
    assert not operation_runs.c.summary.nullable
    assert str(operation_runs.c.summary.server_default.arg) == "'{}'::jsonb"

    ddl = str(CreateTable(operation_runs).compile(dialect=postgresql.dialect()))
    assert "ck_operation_runs_type" in ddl
    assert "ck_operation_runs_status" in ddl
    assert "ck_operation_runs_trigger" in ddl
    assert "ck_operation_runs_local_status" in ddl
    assert "ck_operation_runs_oss_status" in ddl

    indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in operation_runs.indexes
    }
    assert set(indexes) == {
        "idx_operation_runs_idempotency_unique",
        "idx_operation_runs_type_created",
        "idx_operation_runs_status_created",
    }
    assert "UNIQUE" in indexes["idx_operation_runs_idempotency_unique"]
    assert "WHERE idempotency_key IS NOT NULL" in indexes[
        "idx_operation_runs_idempotency_unique"
    ]


def test_platform_operations_migration_contract():
    migration = (
        Path(__file__).parents[1]
        / "app/db/migrations/versions/20260812_0011_platform_operations.py"
    ).read_text(encoding="utf-8")
    compact = " ".join(migration.split())

    assert 'revision = "20260812_0011"' in migration
    assert 'down_revision = "20260812_0010"' in migration
    for token in (
        'sa.Column("backup_enabled"',
        'sa.Column("backup_oss_access_key_id_encrypted"',
        'sa.Column("webhook_url_encrypted"',
        'op.add_column("platform_settings", column)',
        'op.create_table( "operation_runs"',
        'op.create_index( "idx_operation_runs_idempotency_unique"',
    ):
        assert token in compact


def test_platform_operations_migration_offline_upgrade_and_downgrade(monkeypatch):
    backend_root = Path(__file__).parents[1]
    monkeypatch.setenv(
        "MIEMIE_DATABASE_URL",
        "postgresql+psycopg://miemie:secret@database.invalid/miemie",
    )

    def render(action):
        output = io.StringIO()
        config = Config(str(backend_root / "alembic.ini"), stdout=output)
        config.set_main_option(
            "script_location", str(backend_root / "app/db/migrations")
        )
        config.output_buffer = output
        action(config)
        return output.getvalue()

    upgrade_sql = render(
        lambda config: command.upgrade(config, "20260812_0010:20260812_0011", sql=True)
    )
    downgrade_sql = render(
        lambda config: command.downgrade(
            config, "20260812_0011:20260812_0010", sql=True
        )
    )

    assert "ALTER TABLE platform_settings ADD COLUMN backup_enabled" in upgrade_sql
    assert "CREATE TABLE operation_runs" in upgrade_sql
    assert "CREATE UNIQUE INDEX idx_operation_runs_idempotency_unique" in upgrade_sql
    assert "DROP TABLE operation_runs" in downgrade_sql
    assert "ALTER TABLE platform_settings DROP COLUMN backup_enabled" in downgrade_sql
    assert "DROP INDEX idx_operation_runs_idempotency_unique" in downgrade_sql
