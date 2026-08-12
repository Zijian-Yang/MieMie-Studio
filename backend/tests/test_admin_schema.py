from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.schema import metadata
from app.db.schema.platform_admin import admin_audit_logs, platform_settings
from app.models.user import User


def test_user_security_defaults_and_validation():
    user = User(username="member", password="hash")

    assert user.role == "member"
    assert user.status == "active"
    assert user.must_change_password is False
    assert user.updated_at

    for field, invalid_value in (("role", "owner"), ("status", "locked")):
        try:
            User(username="invalid", password="hash", **{field: invalid_value})
        except ValueError:
            continue
        raise AssertionError(f"invalid {field} must be rejected")


def test_platform_settings_schema_is_singleton_and_secret_safe():
    assert metadata.tables["platform_settings"] is platform_settings
    assert set(platform_settings.c.keys()) == {
        "id",
        "registration_enabled",
        "created_at",
        "updated_at",
        "updated_by",
    }
    assert platform_settings.c.id.primary_key
    assert str(platform_settings.c.registration_enabled.server_default.arg) == "false"

    ddl = str(CreateTable(platform_settings).compile(dialect=postgresql.dialect()))
    assert "registration_enabled BOOLEAN DEFAULT false NOT NULL" in ddl
    assert "password" not in ddl.lower()
    assert "token" not in ddl.lower()


def test_admin_audit_schema_contains_safe_query_fields():
    assert metadata.tables["admin_audit_logs"] is admin_audit_logs
    assert set(admin_audit_logs.c.keys()) == {
        "id",
        "actor_user_id",
        "action",
        "target_type",
        "target_id",
        "request_id",
        "result",
        "changes",
        "created_at",
    }
    assert admin_audit_logs.c.id.primary_key
    assert not admin_audit_logs.c.changes.nullable
    assert str(admin_audit_logs.c.changes.server_default.arg) == "'{}'::jsonb"

    indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in admin_audit_logs.indexes
    }
    assert set(indexes) == {
        "idx_admin_audit_actor_created",
        "idx_admin_audit_action_created",
        "idx_admin_audit_target_created",
    }
    assert "actor_user_id, created_at DESC" in indexes["idx_admin_audit_actor_created"]
    assert "action, created_at DESC" in indexes["idx_admin_audit_action_created"]
    assert "target_type, target_id, created_at DESC" in indexes[
        "idx_admin_audit_target_created"
    ]


def test_admin_governance_migration_contract():
    migration = (
        Path(__file__).parents[1]
        / "app/db/migrations/versions/20260812_0010_admin_governance.py"
    ).read_text(encoding="utf-8")
    compact = " ".join(migration.split())

    assert 'revision = "20260812_0010"' in migration
    assert 'down_revision = "20260617_0009"' in migration
    for token in (
        'sa.Column("role"',
        'sa.Column("status"',
        'sa.Column("must_change_password"',
        'op.create_table( "platform_settings"',
        'op.create_table( "admin_audit_logs"',
    ):
        assert token in compact
