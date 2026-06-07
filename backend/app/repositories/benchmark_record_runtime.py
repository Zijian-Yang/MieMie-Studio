"""Runtime feature flags for benchmark record PostgreSQL shadow writes."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

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
