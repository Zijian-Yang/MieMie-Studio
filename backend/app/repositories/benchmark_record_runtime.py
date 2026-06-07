"""Runtime feature flags for benchmark record PostgreSQL shadow writes."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Callable

from sqlalchemy.pool import NullPool

from app.db.engine import TRUE_VALUES, create_database_engine, database_enabled
from app.repositories.benchmark_records import BenchmarkRecord, PostgresBenchmarkRecordRepository


logger = logging.getLogger(__name__)

DOMAIN = "benchmark_records"


def _env_csv(name: str) -> set[str]:
    return {
        item.strip()
        for item in os.getenv(name, "").split(",")
        if item.strip()
    }


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def benchmark_record_dual_write_enabled() -> bool:
    """Return true when benchmark record shadow writes are explicitly enabled."""

    if not database_enabled():
        return False

    write_mode = os.getenv("MIEMIE_DATABASE_WRITE_MODE", "file").strip().lower()
    dual_domains = _env_csv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS")
    return write_mode in {"dual", "dual_write"} or DOMAIN in dual_domains


def benchmark_record_read_enabled() -> bool:
    """Return true when benchmark record reads should prefer PostgreSQL."""

    if not database_enabled():
        return False

    read_mode = os.getenv("MIEMIE_DATABASE_READ_MODE", "file").strip().lower()
    read_domains = _env_csv("MIEMIE_DATABASE_READ_DOMAINS")
    return read_mode == "postgres" or DOMAIN in read_domains


def benchmark_record_primary_write_enabled() -> bool:
    """Return true when benchmark record writes should use PostgreSQL primary."""

    if not database_enabled():
        return False

    write_mode = os.getenv("MIEMIE_DATABASE_WRITE_MODE", "file").strip().lower()
    primary_domains = _env_csv("MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS")
    return write_mode in {"postgres", "postgres_primary", "primary"} or DOMAIN in primary_domains


def json_fallback_read_enabled() -> bool:
    """Return true when PostgreSQL read miss/error should fallback to JSON."""

    return _env_true("MIEMIE_DATABASE_JSON_FALLBACK_READ")


def json_archive_writes_enabled() -> bool:
    """Return true when PostgreSQL primary writes should maintain JSON archive mirrors."""

    return _env_true("MIEMIE_DATABASE_JSON_ARCHIVE_WRITES")


def strict_shadow_writes_enabled() -> bool:
    """Return true when PostgreSQL shadow write failures should be propagated."""

    return _env_true("MIEMIE_DATABASE_RECONCILE_STRICT")


@lru_cache(maxsize=1)
def _runtime_engine():
    return create_database_engine(poolclass=NullPool, pool_pre_ping=True)


def clear_runtime_database_engine() -> None:
    """Dispose and clear the cached runtime engine, mainly for tests and shutdown hooks."""

    engine = _runtime_engine.cache_info().currsize and _runtime_engine()
    if engine:
        engine.dispose()
    _runtime_engine.cache_clear()


def build_benchmark_record_shadow_repository(user_id: str) -> PostgresBenchmarkRecordRepository:
    return PostgresBenchmarkRecordRepository(_runtime_engine(), user_id)


def build_benchmark_record_read_repository(user_id: str) -> PostgresBenchmarkRecordRepository:
    return PostgresBenchmarkRecordRepository(_runtime_engine(), user_id)


def build_benchmark_record_primary_repository(user_id: str) -> PostgresBenchmarkRecordRepository:
    return PostgresBenchmarkRecordRepository(_runtime_engine(), user_id)


def save_benchmark_record_primary(
    user_id: str | None,
    benchmark_kind: str,
    record_kind: str,
    record: BenchmarkRecord,
) -> bool:
    """Save a benchmark record to PostgreSQL as the primary store when enabled."""

    if not user_id or not benchmark_record_primary_write_enabled():
        return False

    build_benchmark_record_primary_repository(user_id).save(benchmark_kind, record_kind, record)
    return True


def mark_benchmark_record_deleted_primary(
    user_id: str | None,
    benchmark_kind: str,
    record_kind: str,
    record_id: str,
) -> bool:
    """Mark a benchmark record deleted in PostgreSQL primary mode."""

    if not user_id or not benchmark_record_primary_write_enabled():
        return False

    build_benchmark_record_primary_repository(user_id).mark_deleted(benchmark_kind, record_kind, record_id)
    return True


def shadow_save_benchmark_record(
    user_id: str | None,
    benchmark_kind: str,
    record_kind: str,
    record: BenchmarkRecord,
) -> None:
    """Shadow-save a benchmark record to PostgreSQL when dual-write is enabled."""

    if not user_id or not benchmark_record_dual_write_enabled():
        return

    try:
        build_benchmark_record_shadow_repository(user_id).save(benchmark_kind, record_kind, record)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "benchmark_record_shadow_save_failed",
            extra={
                "user_id": user_id,
                "benchmark_kind": benchmark_kind,
                "record_kind": record_kind,
                "record_id": record.id,
                "error": exc.__class__.__name__,
            },
        )


def shadow_mark_benchmark_record_deleted(
    user_id: str | None,
    benchmark_kind: str,
    record_kind: str,
    record_id: str,
) -> None:
    """Shadow-mark a benchmark record deleted when dual-write is enabled."""

    if not user_id or not benchmark_record_dual_write_enabled():
        return

    try:
        build_benchmark_record_shadow_repository(user_id).mark_deleted(benchmark_kind, record_kind, record_id)
    except Exception as exc:
        if strict_shadow_writes_enabled():
            raise
        logger.warning(
            "benchmark_record_shadow_delete_failed",
            extra={
                "user_id": user_id,
                "benchmark_kind": benchmark_kind,
                "record_kind": record_kind,
                "record_id": record_id,
                "error": exc.__class__.__name__,
            },
        )


def read_benchmark_record(
    user_id: str | None,
    benchmark_kind: str,
    record_kind: str,
    record_id: str,
    json_loader: Callable[[], BenchmarkRecord | None],
) -> BenchmarkRecord | None:
    """Read one benchmark record from PostgreSQL when enabled."""

    if not user_id or not benchmark_record_read_enabled():
        return json_loader()

    try:
        record = build_benchmark_record_read_repository(user_id).get(benchmark_kind, record_kind, record_id)
        if record is not None:
            return record
        if json_fallback_read_enabled():
            logger.warning(
                "benchmark_record_postgres_read_miss_json_fallback",
                extra={
                    "user_id": user_id,
                    "benchmark_kind": benchmark_kind,
                    "record_kind": record_kind,
                    "record_id": record_id,
                },
            )
            return json_loader()
        return None
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "benchmark_record_postgres_read_failed_json_fallback",
            extra={
                "user_id": user_id,
                "benchmark_kind": benchmark_kind,
                "record_kind": record_kind,
                "record_id": record_id,
                "error": exc.__class__.__name__,
            },
        )
        return json_loader()


def read_benchmark_records_for_project(
    user_id: str | None,
    benchmark_kind: str,
    record_kind: str,
    project_id: str,
    json_loader: Callable[[], list[BenchmarkRecord]],
) -> list[BenchmarkRecord]:
    """Read benchmark records for a project from PostgreSQL when enabled."""

    if not user_id or not benchmark_record_read_enabled():
        return json_loader()

    try:
        records = build_benchmark_record_read_repository(user_id).list_for_project(
            benchmark_kind,
            record_kind,
            project_id,
        )
        if records or not json_fallback_read_enabled():
            return records
        logger.warning(
            "benchmark_record_postgres_project_empty_json_fallback",
            extra={"user_id": user_id, "benchmark_kind": benchmark_kind, "record_kind": record_kind, "project_id": project_id},
        )
        return json_loader()
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "benchmark_record_postgres_project_read_failed_json_fallback",
            extra={
                "user_id": user_id,
                "benchmark_kind": benchmark_kind,
                "record_kind": record_kind,
                "project_id": project_id,
                "error": exc.__class__.__name__,
            },
        )
        return json_loader()


def read_benchmark_runs_for_suite(
    user_id: str | None,
    benchmark_kind: str,
    suite_id: str,
    json_loader: Callable[[], list[BenchmarkRecord]],
) -> list[BenchmarkRecord]:
    """Read benchmark runs for a suite from PostgreSQL when enabled."""

    if not user_id or not benchmark_record_read_enabled():
        return json_loader()

    try:
        records = build_benchmark_record_read_repository(user_id).list_runs_for_suite(benchmark_kind, suite_id)
        if records or not json_fallback_read_enabled():
            return records
        logger.warning(
            "benchmark_record_postgres_suite_empty_json_fallback",
            extra={"user_id": user_id, "benchmark_kind": benchmark_kind, "suite_id": suite_id},
        )
        return json_loader()
    except Exception as exc:
        if not json_fallback_read_enabled():
            raise
        logger.warning(
            "benchmark_record_postgres_suite_read_failed_json_fallback",
            extra={"user_id": user_id, "benchmark_kind": benchmark_kind, "suite_id": suite_id, "error": exc.__class__.__name__},
        )
        return json_loader()
