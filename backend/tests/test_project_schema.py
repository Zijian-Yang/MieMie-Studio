from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.schema import metadata
from app.db.schema.projects import projects


def test_projects_schema_columns_and_defaults():
    assert metadata.tables["projects"] is projects

    expected_columns = {
        "id",
        "user_id",
        "name",
        "description",
        "has_script",
        "script_shot_count",
        "character_count",
        "scene_count",
        "prop_count",
        "style_count",
        "llm_configs",
        "raw_project_snapshot",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert set(projects.c.keys()) == expected_columns
    assert projects.c.id.primary_key
    assert not projects.c.user_id.nullable
    assert not projects.c.name.nullable
    assert not projects.c.raw_project_snapshot.nullable
    assert str(projects.c.llm_configs.server_default.arg) == "'{}'::jsonb"
    assert str(projects.c.raw_project_snapshot.server_default.arg) == "'{}'::jsonb"


def test_projects_postgresql_ddl_contains_jsonb_and_timestamptz():
    ddl = str(CreateTable(projects).compile(dialect=postgresql.dialect()))

    assert "CREATE TABLE projects" in ddl
    assert "llm_configs JSONB DEFAULT '{}'::jsonb NOT NULL" in ddl
    assert "raw_project_snapshot JSONB DEFAULT '{}'::jsonb NOT NULL" in ddl
    assert "created_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl
    assert "updated_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl


def test_projects_partial_indexes():
    compiled_indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in projects.indexes
    }

    assert set(compiled_indexes) == {
        "idx_projects_user_updated",
        "idx_projects_user_name",
    }
    assert "user_id, updated_at DESC" in compiled_indexes["idx_projects_user_updated"]
    assert "WHERE deleted_at IS NULL" in compiled_indexes["idx_projects_user_updated"]
    assert "user_id, name" in compiled_indexes["idx_projects_user_name"]
    assert "WHERE deleted_at IS NULL" in compiled_indexes["idx_projects_user_name"]
