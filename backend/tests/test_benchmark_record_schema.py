from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.schema import metadata
from app.db.schema.benchmark_records import benchmark_records


def test_benchmark_records_schema_columns_and_defaults():
    assert metadata.tables["benchmark_records"] is benchmark_records

    expected_columns = {
        "id",
        "benchmark_kind",
        "record_kind",
        "user_id",
        "project_id",
        "dataset_id",
        "suite_id",
        "task_kind",
        "status",
        "name",
        "item_count",
        "cell_count",
        "raw_record_snapshot",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
        "deleted_at",
    }
    assert set(benchmark_records.c.keys()) == expected_columns
    assert benchmark_records.c.id.primary_key
    assert benchmark_records.c.benchmark_kind.primary_key
    assert benchmark_records.c.record_kind.primary_key
    assert not benchmark_records.c.user_id.nullable
    assert not benchmark_records.c.project_id.nullable
    assert not benchmark_records.c.raw_record_snapshot.nullable
    assert str(benchmark_records.c.raw_record_snapshot.server_default.arg) == "'{}'::jsonb"


def test_benchmark_records_postgresql_ddl_contains_composite_pk_jsonb_and_timestamptz():
    ddl = str(CreateTable(benchmark_records).compile(dialect=postgresql.dialect()))

    assert "CREATE TABLE benchmark_records" in ddl
    assert "PRIMARY KEY (id, benchmark_kind, record_kind)" in ddl
    assert "raw_record_snapshot JSONB DEFAULT '{}'::jsonb NOT NULL" in ddl
    assert "created_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl
    assert "updated_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl


def test_benchmark_records_partial_indexes():
    compiled_indexes = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in benchmark_records.indexes
    }

    assert set(compiled_indexes) == {
        "idx_benchmark_records_user_project_kind_updated",
        "idx_benchmark_records_user_suite_runs",
        "idx_benchmark_records_user_dataset_suites",
    }
    assert "user_id, project_id, benchmark_kind, record_kind, updated_at DESC" in compiled_indexes[
        "idx_benchmark_records_user_project_kind_updated"
    ]
    assert "user_id, benchmark_kind, suite_id, created_at DESC" in compiled_indexes[
        "idx_benchmark_records_user_suite_runs"
    ]
    assert "user_id, benchmark_kind, dataset_id, updated_at DESC" in compiled_indexes[
        "idx_benchmark_records_user_dataset_suites"
    ]
    assert "WHERE deleted_at IS NULL" in compiled_indexes[
        "idx_benchmark_records_user_project_kind_updated"
    ]
