"""Repositories for benchmark datasets, suites, and runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.db.schema.benchmark_records import benchmark_records
from app.models.image_benchmark import ImageBenchmarkDataset, ImageBenchmarkRun, ImageBenchmarkSuite
from app.models.video_benchmark import VideoBenchmarkDataset, VideoBenchmarkRun, VideoBenchmarkSuite
from app.repositories.base import RepositoryWriteError
from app.services.storage import StorageService


BENCHMARK_IMAGE = "image"
BENCHMARK_VIDEO = "video"
RECORD_DATASET = "dataset"
RECORD_SUITE = "suite"
RECORD_RUN = "run"

BenchmarkRecord = (
    ImageBenchmarkDataset
    | ImageBenchmarkSuite
    | ImageBenchmarkRun
    | VideoBenchmarkDataset
    | VideoBenchmarkSuite
    | VideoBenchmarkRun
)

_RECORD_MODELS: dict[tuple[str, str], type[BenchmarkRecord]] = {
    (BENCHMARK_IMAGE, RECORD_DATASET): ImageBenchmarkDataset,
    (BENCHMARK_IMAGE, RECORD_SUITE): ImageBenchmarkSuite,
    (BENCHMARK_IMAGE, RECORD_RUN): ImageBenchmarkRun,
    (BENCHMARK_VIDEO, RECORD_DATASET): VideoBenchmarkDataset,
    (BENCHMARK_VIDEO, RECORD_SUITE): VideoBenchmarkSuite,
    (BENCHMARK_VIDEO, RECORD_RUN): VideoBenchmarkRun,
}


def _ensure_supported(benchmark_kind: str, record_kind: str) -> type[BenchmarkRecord]:
    model = _RECORD_MODELS.get((benchmark_kind, record_kind))
    if model is None:
        raise ValueError(f"Unsupported benchmark record kind: {benchmark_kind}/{record_kind}")
    return model


def _status(record: BenchmarkRecord) -> str | None:
    value = getattr(record, "status", None)
    return getattr(value, "value", value)


def _item_count(record_kind: str, record: BenchmarkRecord) -> int:
    if record_kind == RECORD_DATASET:
        return len(getattr(record, "items", []) or [])
    return 0


def _cell_count(record_kind: str, record: BenchmarkRecord) -> int:
    if record_kind == RECORD_RUN:
        return len(getattr(record, "cell_results", []) or [])
    return 0


def benchmark_record_to_row(
    user_id: str,
    benchmark_kind: str,
    record_kind: str,
    record: BenchmarkRecord,
) -> dict[str, Any]:
    """Convert a benchmark Pydantic model into indexed PostgreSQL columns."""

    _ensure_supported(benchmark_kind, record_kind)
    return {
        "id": record.id,
        "benchmark_kind": benchmark_kind,
        "record_kind": record_kind,
        "user_id": user_id,
        "project_id": record.project_id,
        "dataset_id": getattr(record, "dataset_id", None),
        "suite_id": getattr(record, "suite_id", None),
        "task_kind": record.task_kind,
        "status": _status(record),
        "name": getattr(record, "name", None),
        "item_count": _item_count(record_kind, record),
        "cell_count": _cell_count(record_kind, record),
        "raw_record_snapshot": record.model_dump(mode="json"),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "started_at": getattr(record, "started_at", None),
        "finished_at": getattr(record, "finished_at", None),
        "deleted_at": None,
    }


def row_to_benchmark_record(row: Mapping[str, Any]) -> BenchmarkRecord:
    """Restore a benchmark model from a PostgreSQL row."""

    model = _ensure_supported(row["benchmark_kind"], row["record_kind"])
    snapshot = row.get("raw_record_snapshot")
    if snapshot:
        return model(**snapshot)

    base: dict[str, Any] = {
        "id": row["id"],
        "project_id": row["project_id"],
        "task_kind": row["task_kind"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if row["record_kind"] == RECORD_SUITE:
        base["name"] = row.get("name") or ""
        base["dataset_id"] = row.get("dataset_id") or ""
    if row["record_kind"] == RECORD_RUN:
        base["dataset_id"] = row.get("dataset_id") or ""
        base["suite_id"] = row.get("suite_id") or ""
        base["status"] = row.get("status") or "pending"
        base["started_at"] = row.get("started_at")
        base["finished_at"] = row.get("finished_at")
    if row["record_kind"] == RECORD_DATASET:
        base["name"] = row.get("name") or ""
    return model(**base)


class FileBenchmarkRecordRepository:
    """Adapter around the current JSON StorageService benchmark implementation."""

    def __init__(self, storage: StorageService):
        self._storage = storage

    def save(self, benchmark_kind: str, record_kind: str, record: BenchmarkRecord) -> None:
        if benchmark_kind == BENCHMARK_IMAGE and record_kind == RECORD_DATASET:
            self._storage.save_image_benchmark_dataset(record)
        elif benchmark_kind == BENCHMARK_IMAGE and record_kind == RECORD_SUITE:
            self._storage.save_image_benchmark_suite(record)
        elif benchmark_kind == BENCHMARK_IMAGE and record_kind == RECORD_RUN:
            self._storage.save_image_benchmark_run(record)
        elif benchmark_kind == BENCHMARK_VIDEO and record_kind == RECORD_DATASET:
            self._storage.save_video_benchmark_dataset(record)
        elif benchmark_kind == BENCHMARK_VIDEO and record_kind == RECORD_SUITE:
            self._storage.save_video_benchmark_suite(record)
        elif benchmark_kind == BENCHMARK_VIDEO and record_kind == RECORD_RUN:
            self._storage.save_video_benchmark_run(record)
        else:
            _ensure_supported(benchmark_kind, record_kind)

    def get(self, benchmark_kind: str, record_kind: str, record_id: str) -> BenchmarkRecord | None:
        if benchmark_kind == BENCHMARK_IMAGE and record_kind == RECORD_DATASET:
            return self._storage.get_image_benchmark_dataset(record_id)
        if benchmark_kind == BENCHMARK_IMAGE and record_kind == RECORD_SUITE:
            return self._storage.get_image_benchmark_suite(record_id)
        if benchmark_kind == BENCHMARK_IMAGE and record_kind == RECORD_RUN:
            return self._storage.get_image_benchmark_run(record_id)
        if benchmark_kind == BENCHMARK_VIDEO and record_kind == RECORD_DATASET:
            return self._storage.get_video_benchmark_dataset(record_id)
        if benchmark_kind == BENCHMARK_VIDEO and record_kind == RECORD_SUITE:
            return self._storage.get_video_benchmark_suite(record_id)
        if benchmark_kind == BENCHMARK_VIDEO and record_kind == RECORD_RUN:
            return self._storage.get_video_benchmark_run(record_id)
        _ensure_supported(benchmark_kind, record_kind)
        return None

    def list_for_project(self, benchmark_kind: str, record_kind: str, project_id: str) -> list[BenchmarkRecord]:
        if benchmark_kind == BENCHMARK_IMAGE and record_kind == RECORD_DATASET:
            return self._storage.get_image_benchmark_datasets(project_id)
        if benchmark_kind == BENCHMARK_IMAGE and record_kind == RECORD_SUITE:
            return self._storage.get_image_benchmark_suites(project_id)
        if benchmark_kind == BENCHMARK_IMAGE and record_kind == RECORD_RUN:
            return self._storage.get_image_benchmark_runs_by_project(project_id)
        if benchmark_kind == BENCHMARK_VIDEO and record_kind == RECORD_DATASET:
            return self._storage.get_video_benchmark_datasets(project_id)
        if benchmark_kind == BENCHMARK_VIDEO and record_kind == RECORD_SUITE:
            return self._storage.get_video_benchmark_suites(project_id)
        if benchmark_kind == BENCHMARK_VIDEO and record_kind == RECORD_RUN:
            return self._storage.get_video_benchmark_runs_by_project(project_id)
        _ensure_supported(benchmark_kind, record_kind)
        return []

    def list_runs_for_suite(self, benchmark_kind: str, suite_id: str) -> list[BenchmarkRecord]:
        if benchmark_kind == BENCHMARK_IMAGE:
            return self._storage.get_image_benchmark_runs_by_suite(suite_id)
        if benchmark_kind == BENCHMARK_VIDEO:
            return self._storage.get_video_benchmark_runs_by_suite(suite_id)
        _ensure_supported(benchmark_kind, RECORD_RUN)
        return []

    def list_runs_for_project(self, benchmark_kind: str, project_id: str) -> list[BenchmarkRecord]:
        return self.list_for_project(benchmark_kind, RECORD_RUN, project_id)

    def delete(self, benchmark_kind: str, record_kind: str, record_id: str) -> None:
        if benchmark_kind == BENCHMARK_IMAGE and record_kind == RECORD_DATASET:
            self._storage.delete_image_benchmark_dataset(record_id)
        elif benchmark_kind == BENCHMARK_IMAGE and record_kind == RECORD_SUITE:
            self._storage.delete_image_benchmark_suite(record_id)
        elif benchmark_kind == BENCHMARK_IMAGE and record_kind == RECORD_RUN:
            self._storage.delete_image_benchmark_run(record_id)
        elif benchmark_kind == BENCHMARK_VIDEO and record_kind == RECORD_DATASET:
            self._storage.delete_video_benchmark_dataset(record_id)
        elif benchmark_kind == BENCHMARK_VIDEO and record_kind == RECORD_SUITE:
            self._storage.delete_video_benchmark_suite(record_id)
        elif benchmark_kind == BENCHMARK_VIDEO and record_kind == RECORD_RUN:
            self._storage.delete_video_benchmark_run(record_id)
        else:
            _ensure_supported(benchmark_kind, record_kind)

    def mark_deleted(self, benchmark_kind: str, record_kind: str, record_id: str) -> None:
        self.delete(benchmark_kind, record_kind, record_id)


class PostgresBenchmarkRecordRepository:
    """PostgreSQL-backed benchmark record repository."""

    def __init__(self, engine, user_id: str):
        self._engine = engine
        self._user_id = user_id

    def save(self, benchmark_kind: str, record_kind: str, record: BenchmarkRecord) -> None:
        row = benchmark_record_to_row(self._user_id, benchmark_kind, record_kind, record)
        stmt = insert(benchmark_records).values(**row)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                benchmark_records.c.id,
                benchmark_records.c.benchmark_kind,
                benchmark_records.c.record_kind,
            ],
            set_={
                "user_id": stmt.excluded.user_id,
                "project_id": stmt.excluded.project_id,
                "dataset_id": stmt.excluded.dataset_id,
                "suite_id": stmt.excluded.suite_id,
                "task_kind": stmt.excluded.task_kind,
                "status": stmt.excluded.status,
                "name": stmt.excluded.name,
                "item_count": stmt.excluded.item_count,
                "cell_count": stmt.excluded.cell_count,
                "raw_record_snapshot": stmt.excluded.raw_record_snapshot,
                "created_at": stmt.excluded.created_at,
                "updated_at": stmt.excluded.updated_at,
                "started_at": stmt.excluded.started_at,
                "finished_at": stmt.excluded.finished_at,
                "deleted_at": None,
            },
        )
        try:
            with self._engine.begin() as conn:
                conn.execute(stmt)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc

    def get(self, benchmark_kind: str, record_kind: str, record_id: str) -> BenchmarkRecord | None:
        _ensure_supported(benchmark_kind, record_kind)
        stmt = select(benchmark_records).where(
            benchmark_records.c.id == record_id,
            benchmark_records.c.benchmark_kind == benchmark_kind,
            benchmark_records.c.record_kind == record_kind,
            benchmark_records.c.user_id == self._user_id,
            benchmark_records.c.deleted_at.is_(None),
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return row_to_benchmark_record(row) if row else None

    def list_for_project(self, benchmark_kind: str, record_kind: str, project_id: str) -> list[BenchmarkRecord]:
        _ensure_supported(benchmark_kind, record_kind)
        order_column = benchmark_records.c.created_at.desc() if record_kind == RECORD_RUN else benchmark_records.c.updated_at.desc()
        stmt = (
            select(benchmark_records)
            .where(
                benchmark_records.c.benchmark_kind == benchmark_kind,
                benchmark_records.c.record_kind == record_kind,
                benchmark_records.c.user_id == self._user_id,
                benchmark_records.c.project_id == project_id,
                benchmark_records.c.deleted_at.is_(None),
            )
            .order_by(order_column)
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [row_to_benchmark_record(row) for row in rows]

    def list_runs_for_suite(self, benchmark_kind: str, suite_id: str) -> list[BenchmarkRecord]:
        _ensure_supported(benchmark_kind, RECORD_RUN)
        stmt = (
            select(benchmark_records)
            .where(
                benchmark_records.c.benchmark_kind == benchmark_kind,
                benchmark_records.c.record_kind == RECORD_RUN,
                benchmark_records.c.user_id == self._user_id,
                benchmark_records.c.suite_id == suite_id,
                benchmark_records.c.deleted_at.is_(None),
            )
            .order_by(benchmark_records.c.created_at.desc())
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [row_to_benchmark_record(row) for row in rows]

    def list_runs_for_project(self, benchmark_kind: str, project_id: str) -> list[BenchmarkRecord]:
        return self.list_for_project(benchmark_kind, RECORD_RUN, project_id)

    def delete(self, benchmark_kind: str, record_kind: str, record_id: str) -> None:
        self.mark_deleted(benchmark_kind, record_kind, record_id)

    def mark_deleted(self, benchmark_kind: str, record_kind: str, record_id: str) -> None:
        _ensure_supported(benchmark_kind, record_kind)
        stmt = (
            update(benchmark_records)
            .where(
                benchmark_records.c.id == record_id,
                benchmark_records.c.benchmark_kind == benchmark_kind,
                benchmark_records.c.record_kind == record_kind,
                benchmark_records.c.user_id == self._user_id,
            )
            .values(deleted_at=datetime.utcnow())
        )
        try:
            with self._engine.begin() as conn:
                conn.execute(stmt)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc
