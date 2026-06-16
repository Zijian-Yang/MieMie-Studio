from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.schema import metadata
from app.db.schema.sessions import sessions


def test_sessions_schema_columns_and_sensitive_naming():
    assert metadata.tables["sessions"] is sessions

    expected_columns = {
        "token_hash",
        "user_id",
        "raw_session_snapshot",
        "created_at",
        "last_seen_at",
        "expires_at",
        "deleted_at",
    }
    assert set(sessions.c.keys()) == expected_columns
    assert sessions.c.token_hash.primary_key
    assert "token" not in set(sessions.c.keys()) - {"token_hash"}
    assert not sessions.c.user_id.nullable
    assert not sessions.c.raw_session_snapshot.nullable
    assert str(sessions.c.raw_session_snapshot.server_default.arg) == "'{}'::jsonb"


def test_sessions_postgresql_ddl_contains_jsonb_and_timestamptz():
    ddl = str(CreateTable(sessions).compile(dialect=postgresql.dialect()))

    assert "CREATE TABLE sessions" in ddl
    assert "token_hash TEXT NOT NULL" in ddl
    assert "raw_session_snapshot JSONB DEFAULT '{}'::jsonb NOT NULL" in ddl
    assert "created_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl
    assert "expires_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl


def test_sessions_partial_indexes():
    compiled_indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in sessions.indexes
    }

    assert set(compiled_indexes) == {
        "idx_sessions_user_active",
        "idx_sessions_expires_active",
    }
    assert "user_id" in compiled_indexes["idx_sessions_user_active"]
    assert "WHERE deleted_at IS NULL" in compiled_indexes["idx_sessions_user_active"]
    assert "expires_at" in compiled_indexes["idx_sessions_expires_active"]
    assert "WHERE deleted_at IS NULL" in compiled_indexes["idx_sessions_expires_active"]
