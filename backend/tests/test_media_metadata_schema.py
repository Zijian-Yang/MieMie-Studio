from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.schema import metadata
from app.db.schema.media_assets import media_assets, text_items


def test_media_assets_schema_columns_and_defaults():
    assert metadata.tables["media_assets"] is media_assets

    expected_columns = {
        "id",
        "user_id",
        "project_id",
        "asset_kind",
        "name",
        "description",
        "url",
        "file_type",
        "file_size",
        "duration",
        "width",
        "height",
        "fps",
        "thumbnail_url",
        "sample_rate",
        "channels",
        "source",
        "task_id",
        "tags",
        "prompt_used",
        "raw_media_snapshot",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert set(media_assets.c.keys()) == expected_columns
    assert media_assets.c.id.primary_key
    assert not media_assets.c.user_id.nullable
    assert not media_assets.c.project_id.nullable
    assert not media_assets.c.asset_kind.nullable
    assert not media_assets.c.url.nullable
    assert str(media_assets.c.tags.server_default.arg) == "'[]'::jsonb"
    assert str(media_assets.c.raw_media_snapshot.server_default.arg) == "'{}'::jsonb"


def test_media_assets_postgresql_ddl_contains_jsonb_and_timestamptz():
    ddl = str(CreateTable(media_assets).compile(dialect=postgresql.dialect()))

    assert "CREATE TABLE media_assets" in ddl
    assert "tags JSONB DEFAULT '[]'::jsonb NOT NULL" in ddl
    assert "raw_media_snapshot JSONB DEFAULT '{}'::jsonb NOT NULL" in ddl
    assert "created_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl
    assert "updated_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl


def test_media_assets_partial_indexes():
    compiled_indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in media_assets.indexes
    }

    assert set(compiled_indexes) == {
        "idx_media_assets_user_project_kind_updated",
        "idx_media_assets_user_url",
        "idx_media_assets_task_id",
    }
    assert "user_id, project_id, asset_kind, updated_at DESC" in compiled_indexes[
        "idx_media_assets_user_project_kind_updated"
    ]
    assert "WHERE deleted_at IS NULL" in compiled_indexes[
        "idx_media_assets_user_project_kind_updated"
    ]
    assert "user_id, url" in compiled_indexes["idx_media_assets_user_url"]
    assert "task_id" in compiled_indexes["idx_media_assets_task_id"]


def test_text_items_schema_columns_and_defaults():
    assert metadata.tables["text_items"] is text_items

    expected_columns = {
        "id",
        "user_id",
        "project_id",
        "name",
        "category",
        "content",
        "version_count",
        "raw_text_snapshot",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert set(text_items.c.keys()) == expected_columns
    assert text_items.c.id.primary_key
    assert not text_items.c.user_id.nullable
    assert not text_items.c.project_id.nullable
    assert not text_items.c.content.nullable
    assert str(text_items.c.raw_text_snapshot.server_default.arg) == "'{}'::jsonb"


def test_text_items_partial_indexes():
    compiled_indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in text_items.indexes
    }

    assert set(compiled_indexes) == {
        "idx_text_items_user_project_updated",
        "idx_text_items_user_category_updated",
    }
    assert "user_id, project_id, updated_at DESC" in compiled_indexes[
        "idx_text_items_user_project_updated"
    ]
    assert "user_id, category, updated_at DESC" in compiled_indexes[
        "idx_text_items_user_category_updated"
    ]
    assert "WHERE deleted_at IS NULL" in compiled_indexes[
        "idx_text_items_user_category_updated"
    ]
