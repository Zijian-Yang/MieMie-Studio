"""Benchmark dataset/suite/run table definitions."""

from sqlalchemy import Column, DateTime, Index, Integer, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.schema import metadata


benchmark_records = Table(
    "benchmark_records",
    metadata,
    Column("id", Text, primary_key=True),
    Column("benchmark_kind", Text, primary_key=True),
    Column("record_kind", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("project_id", Text, nullable=False),
    Column("dataset_id", Text, nullable=True),
    Column("suite_id", Text, nullable=True),
    Column("task_kind", Text, nullable=False),
    Column("status", Text, nullable=True),
    Column("name", Text, nullable=True),
    Column("item_count", Integer, nullable=False, server_default="0"),
    Column("cell_count", Integer, nullable=False, server_default="0"),
    Column("raw_record_snapshot", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

Index(
    "idx_benchmark_records_user_project_kind_updated",
    benchmark_records.c.user_id,
    benchmark_records.c.project_id,
    benchmark_records.c.benchmark_kind,
    benchmark_records.c.record_kind,
    benchmark_records.c.updated_at.desc(),
    postgresql_where=benchmark_records.c.deleted_at.is_(None),
)
Index(
    "idx_benchmark_records_user_suite_runs",
    benchmark_records.c.user_id,
    benchmark_records.c.benchmark_kind,
    benchmark_records.c.suite_id,
    benchmark_records.c.created_at.desc(),
    postgresql_where=benchmark_records.c.deleted_at.is_(None),
)
Index(
    "idx_benchmark_records_user_dataset_suites",
    benchmark_records.c.user_id,
    benchmark_records.c.benchmark_kind,
    benchmark_records.c.dataset_id,
    benchmark_records.c.updated_at.desc(),
    postgresql_where=benchmark_records.c.deleted_at.is_(None),
)
