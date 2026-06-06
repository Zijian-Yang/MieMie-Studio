from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.schema import metadata
from app.db.schema.video_studio_tasks import video_studio_tasks


def test_video_studio_tasks_schema_columns_and_defaults():
    assert metadata.tables["video_studio_tasks"] is video_studio_tasks

    expected_columns = {
        "id",
        "user_id",
        "project_id",
        "task_kind",
        "task_type",
        "provider",
        "key_profile",
        "model_id",
        "model",
        "name",
        "status",
        "submit_state",
        "progress",
        "group_count",
        "prompt",
        "negative_prompt",
        "input_assets",
        "normalized_params",
        "provider_payload_snapshot",
        "provider_result_meta",
        "task_ids",
        "request_ids",
        "video_urls",
        "selected_video_url",
        "thumbnail_url",
        "error_message",
        "submit_attempt_id",
        "submit_started_at",
        "raw_task_snapshot",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert set(video_studio_tasks.c.keys()) == expected_columns
    assert video_studio_tasks.c.id.primary_key
    assert not video_studio_tasks.c.user_id.nullable
    assert not video_studio_tasks.c.project_id.nullable
    assert not video_studio_tasks.c.status.nullable
    assert not video_studio_tasks.c.raw_task_snapshot.nullable
    assert str(video_studio_tasks.c.raw_task_snapshot.server_default.arg) == "'{}'::jsonb"


def test_video_studio_tasks_postgresql_ddl_contains_jsonb_and_timestamptz():
    ddl = str(CreateTable(video_studio_tasks).compile(dialect=postgresql.dialect()))

    assert "CREATE TABLE video_studio_tasks" in ddl
    assert "input_assets JSONB DEFAULT '{}'::jsonb NOT NULL" in ddl
    assert "raw_task_snapshot JSONB DEFAULT '{}'::jsonb NOT NULL" in ddl
    assert "created_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl
    assert "updated_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl


def test_video_studio_tasks_partial_indexes():
    compiled_indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in video_studio_tasks.indexes
    }

    assert set(compiled_indexes) == {
        "idx_video_studio_tasks_user_project_updated",
        "idx_video_studio_tasks_user_status_updated",
        "idx_video_studio_tasks_submit_attempt",
    }
    assert "user_id, project_id, updated_at DESC" in compiled_indexes[
        "idx_video_studio_tasks_user_project_updated"
    ]
    assert "WHERE deleted_at IS NULL" in compiled_indexes[
        "idx_video_studio_tasks_user_project_updated"
    ]
    assert "user_id, status, updated_at DESC" in compiled_indexes[
        "idx_video_studio_tasks_user_status_updated"
    ]
    assert "WHERE deleted_at IS NULL" in compiled_indexes[
        "idx_video_studio_tasks_user_status_updated"
    ]
    assert "submit_attempt_id" in compiled_indexes["idx_video_studio_tasks_submit_attempt"]
    assert "WHERE submit_attempt_id IS NOT NULL" in compiled_indexes[
        "idx_video_studio_tasks_submit_attempt"
    ]
