from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.schema import metadata
from app.db.schema.user_config import user_configs, users


def test_users_schema_columns_defaults_and_sensitive_naming():
    assert metadata.tables["users"] is users

    expected_columns = {
        "id",
        "username",
        "password_hash",
        "display_name",
        "raw_user_snapshot",
        "created_at",
        "updated_at",
        "last_login",
        "deleted_at",
    }
    assert set(users.c.keys()) == expected_columns
    assert users.c.id.primary_key
    assert not users.c.username.nullable
    assert not users.c.password_hash.nullable
    assert not users.c.raw_user_snapshot.nullable
    assert str(users.c.raw_user_snapshot.server_default.arg) == "'{}'::jsonb"


def test_user_configs_schema_columns_defaults_and_safe_indexes():
    assert metadata.tables["user_configs"] is user_configs

    expected_columns = {
        "user_id",
        "raw_config_snapshot",
        "api_region",
        "has_dashscope_key",
        "has_oss_config",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert set(user_configs.c.keys()) == expected_columns
    assert user_configs.c.user_id.primary_key
    assert not user_configs.c.raw_config_snapshot.nullable
    assert str(user_configs.c.raw_config_snapshot.server_default.arg) == "'{}'::jsonb"
    assert not user_configs.c.has_dashscope_key.nullable
    assert not user_configs.c.has_oss_config.nullable


def test_user_config_postgresql_ddl_contains_jsonb_timestamptz_and_booleans():
    users_ddl = str(CreateTable(users).compile(dialect=postgresql.dialect()))
    configs_ddl = str(CreateTable(user_configs).compile(dialect=postgresql.dialect()))

    assert "CREATE TABLE users" in users_ddl
    assert "password_hash TEXT NOT NULL" in users_ddl
    assert "raw_user_snapshot JSONB DEFAULT '{}'::jsonb NOT NULL" in users_ddl
    assert "created_at TIMESTAMP WITH TIME ZONE NOT NULL" in users_ddl
    assert "last_login TIMESTAMP WITH TIME ZONE" in users_ddl

    assert "CREATE TABLE user_configs" in configs_ddl
    assert "raw_config_snapshot JSONB DEFAULT '{}'::jsonb NOT NULL" in configs_ddl
    assert "has_dashscope_key BOOLEAN DEFAULT false NOT NULL" in configs_ddl
    assert "has_oss_config BOOLEAN DEFAULT false NOT NULL" in configs_ddl


def test_user_config_partial_indexes():
    user_indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in users.indexes
    }
    config_indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in user_configs.indexes
    }

    assert set(user_indexes) == {
        "idx_users_username_active_unique",
        "idx_users_updated",
    }
    assert "UNIQUE" in user_indexes["idx_users_username_active_unique"]
    assert "username" in user_indexes["idx_users_username_active_unique"]
    assert "WHERE deleted_at IS NULL" in user_indexes["idx_users_username_active_unique"]
    assert "updated_at DESC" in user_indexes["idx_users_updated"]

    assert set(config_indexes) == {
        "idx_user_configs_updated",
        "idx_user_configs_api_region",
    }
    assert "updated_at DESC" in config_indexes["idx_user_configs_updated"]
    assert "api_region" in config_indexes["idx_user_configs_api_region"]
