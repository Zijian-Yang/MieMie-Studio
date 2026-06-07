from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.schema import metadata
from app.db.schema.project_entities import project_entities


def test_project_entities_schema_columns_and_defaults():
    assert metadata.tables["project_entities"] is project_entities

    expected_columns = {
        "id",
        "entity_kind",
        "user_id",
        "project_id",
        "name",
        "shot_id",
        "shot_number",
        "status",
        "thumbnail_url",
        "selected_group_index",
        "raw_entity_snapshot",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert set(project_entities.c.keys()) == expected_columns
    assert project_entities.c.id.primary_key
    assert project_entities.c.entity_kind.primary_key
    assert not project_entities.c.user_id.nullable
    assert not project_entities.c.project_id.nullable
    assert not project_entities.c.raw_entity_snapshot.nullable
    assert str(project_entities.c.raw_entity_snapshot.server_default.arg) == "'{}'::jsonb"


def test_project_entities_postgresql_ddl_contains_composite_pk_jsonb_and_timestamptz():
    ddl = str(CreateTable(project_entities).compile(dialect=postgresql.dialect()))

    assert "CREATE TABLE project_entities" in ddl
    assert "PRIMARY KEY (id, entity_kind)" in ddl
    assert "raw_entity_snapshot JSONB DEFAULT '{}'::jsonb NOT NULL" in ddl
    assert "created_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl
    assert "updated_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl


def test_project_entities_partial_indexes():
    compiled_indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in project_entities.indexes
    }

    assert set(compiled_indexes) == {
        "idx_project_entities_user_project_kind_updated",
        "idx_project_entities_user_kind_name",
        "idx_project_entities_user_project_kind_shot",
    }
    assert "user_id, project_id, entity_kind, updated_at DESC" in compiled_indexes[
        "idx_project_entities_user_project_kind_updated"
    ]
    assert "user_id, entity_kind, name" in compiled_indexes[
        "idx_project_entities_user_kind_name"
    ]
    assert "user_id, project_id, entity_kind, shot_id, shot_number" in compiled_indexes[
        "idx_project_entities_user_project_kind_shot"
    ]
    assert "WHERE deleted_at IS NULL" in compiled_indexes[
        "idx_project_entities_user_project_kind_updated"
    ]
