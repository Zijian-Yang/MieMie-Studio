from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.schema import metadata
from app.db.schema.studio_tasks import studio_tasks


def test_studio_tasks_schema_columns_and_defaults():
    assert metadata.tables["studio_tasks"] is studio_tasks

    expected_columns = {
        "id",
        "user_id",
        "project_id",
        "task_kind",
        "provider",
        "model_id",
        "model",
        "name",
        "status",
        "group_count",
        "image_count",
        "selected_image_count",
        "prompt",
        "negative_prompt",
        "input_assets",
        "normalized_params",
        "provider_payload_snapshot",
        "provider_result_meta",
        "task_ids",
        "request_ids",
        "images",
        "warnings",
        "error_message",
        "last_task_id",
        "last_request_id",
        "raw_task_snapshot",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert set(studio_tasks.c.keys()) == expected_columns
    assert studio_tasks.c.id.primary_key
    assert not studio_tasks.c.user_id.nullable
    assert not studio_tasks.c.project_id.nullable
    assert not studio_tasks.c.status.nullable
    assert not studio_tasks.c.raw_task_snapshot.nullable
    assert str(studio_tasks.c.raw_task_snapshot.server_default.arg) == "'{}'::jsonb"


def test_studio_tasks_postgresql_ddl_contains_jsonb_and_timestamptz():
    ddl = str(CreateTable(studio_tasks).compile(dialect=postgresql.dialect()))

    assert "CREATE TABLE studio_tasks" in ddl
    assert "images JSONB DEFAULT '[]'::jsonb NOT NULL" in ddl
    assert "raw_task_snapshot JSONB DEFAULT '{}'::jsonb NOT NULL" in ddl
    assert "created_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl
    assert "updated_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl


def test_studio_tasks_partial_indexes():
    compiled_indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in studio_tasks.indexes
    }

    assert set(compiled_indexes) == {
        "idx_studio_tasks_user_project_updated",
        "idx_studio_tasks_user_status_updated",
    }
    assert "user_id, project_id, updated_at DESC" in compiled_indexes[
        "idx_studio_tasks_user_project_updated"
    ]
    assert "WHERE deleted_at IS NULL" in compiled_indexes[
        "idx_studio_tasks_user_project_updated"
    ]
    assert "user_id, status, updated_at DESC" in compiled_indexes[
        "idx_studio_tasks_user_status_updated"
    ]
    assert "WHERE deleted_at IS NULL" in compiled_indexes[
        "idx_studio_tasks_user_status_updated"
    ]
