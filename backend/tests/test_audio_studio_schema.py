from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.schema import metadata
from app.db.schema.audio_studio import audio_studio_tasks, voice_profiles


def test_audio_studio_tasks_schema_columns_and_defaults():
    assert metadata.tables["audio_studio_tasks"] is audio_studio_tasks

    expected_columns = {
        "id",
        "user_id",
        "project_id",
        "task_type",
        "name",
        "status",
        "voice",
        "format",
        "result_audio_url",
        "result_voice_id",
        "audio_duration",
        "saved_to_library",
        "request_id",
        "markers",
        "error_message",
        "raw_task_snapshot",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert set(audio_studio_tasks.c.keys()) == expected_columns
    assert audio_studio_tasks.c.id.primary_key
    assert not audio_studio_tasks.c.user_id.nullable
    assert not audio_studio_tasks.c.project_id.nullable
    assert not audio_studio_tasks.c.task_type.nullable
    assert not audio_studio_tasks.c.status.nullable
    assert not audio_studio_tasks.c.raw_task_snapshot.nullable
    assert str(audio_studio_tasks.c.markers.server_default.arg) == "'[]'::jsonb"
    assert str(audio_studio_tasks.c.raw_task_snapshot.server_default.arg) == "'{}'::jsonb"


def test_voice_profiles_schema_columns_and_defaults():
    assert metadata.tables["voice_profiles"] is voice_profiles

    expected_columns = {
        "id",
        "user_id",
        "project_id",
        "voice_id",
        "name",
        "source",
        "target_model",
        "prefix",
        "status",
        "preview_audio_url",
        "audio_url",
        "raw_profile_snapshot",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert set(voice_profiles.c.keys()) == expected_columns
    assert voice_profiles.c.id.primary_key
    assert not voice_profiles.c.user_id.nullable
    assert not voice_profiles.c.project_id.nullable
    assert not voice_profiles.c.voice_id.nullable
    assert not voice_profiles.c.source.nullable
    assert not voice_profiles.c.raw_profile_snapshot.nullable
    assert str(voice_profiles.c.raw_profile_snapshot.server_default.arg) == "'{}'::jsonb"


def test_audio_studio_postgresql_ddl_contains_jsonb_and_timestamptz():
    task_ddl = str(CreateTable(audio_studio_tasks).compile(dialect=postgresql.dialect()))
    profile_ddl = str(CreateTable(voice_profiles).compile(dialect=postgresql.dialect()))

    assert "CREATE TABLE audio_studio_tasks" in task_ddl
    assert "markers JSONB DEFAULT '[]'::jsonb NOT NULL" in task_ddl
    assert "raw_task_snapshot JSONB DEFAULT '{}'::jsonb NOT NULL" in task_ddl
    assert "created_at TIMESTAMP WITH TIME ZONE NOT NULL" in task_ddl
    assert "CREATE TABLE voice_profiles" in profile_ddl
    assert "raw_profile_snapshot JSONB DEFAULT '{}'::jsonb NOT NULL" in profile_ddl
    assert "updated_at TIMESTAMP WITH TIME ZONE NOT NULL" in profile_ddl


def test_audio_studio_partial_indexes():
    task_indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in audio_studio_tasks.indexes
    }
    profile_indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in voice_profiles.indexes
    }

    assert set(task_indexes) == {
        "idx_audio_studio_tasks_user_project_updated",
        "idx_audio_studio_tasks_user_status_updated",
        "idx_audio_studio_tasks_user_result_voice",
    }
    assert "user_id, project_id, updated_at DESC" in task_indexes[
        "idx_audio_studio_tasks_user_project_updated"
    ]
    assert "WHERE deleted_at IS NULL" in task_indexes[
        "idx_audio_studio_tasks_user_project_updated"
    ]
    assert "user_id, status, updated_at DESC" in task_indexes[
        "idx_audio_studio_tasks_user_status_updated"
    ]
    assert "user_id, result_voice_id" in task_indexes[
        "idx_audio_studio_tasks_user_result_voice"
    ]

    assert set(profile_indexes) == {
        "idx_voice_profiles_user_project_updated",
        "idx_voice_profiles_user_voice_id",
        "idx_voice_profiles_user_status_updated",
    }
    assert "user_id, project_id, updated_at DESC" in profile_indexes[
        "idx_voice_profiles_user_project_updated"
    ]
    assert "user_id, voice_id" in profile_indexes["idx_voice_profiles_user_voice_id"]
    assert "user_id, status, updated_at DESC" in profile_indexes[
        "idx_voice_profiles_user_status_updated"
    ]
