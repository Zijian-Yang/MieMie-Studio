"""Backfill benchmark JSON files into PostgreSQL repositories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from app.models.image_benchmark import ImageBenchmarkDataset, ImageBenchmarkRun, ImageBenchmarkSuite
from app.models.video_benchmark import VideoBenchmarkDataset, VideoBenchmarkRun, VideoBenchmarkSuite
from app.repositories.benchmark_records import (
    BENCHMARK_IMAGE,
    BENCHMARK_VIDEO,
    RECORD_DATASET,
    RECORD_RUN,
    RECORD_SUITE,
    BenchmarkRecord,
)


RepositoryFactory = Callable[[str], object]

RECORD_DIRECTORIES: dict[tuple[str, str], str] = {
    (BENCHMARK_IMAGE, RECORD_DATASET): "image_benchmark_datasets",
    (BENCHMARK_IMAGE, RECORD_SUITE): "image_benchmark_suites",
    (BENCHMARK_IMAGE, RECORD_RUN): "image_benchmark_runs",
    (BENCHMARK_VIDEO, RECORD_DATASET): "video_benchmark_datasets",
    (BENCHMARK_VIDEO, RECORD_SUITE): "video_benchmark_suites",
    (BENCHMARK_VIDEO, RECORD_RUN): "video_benchmark_runs",
}
RECORD_MODELS: dict[tuple[str, str], type[BenchmarkRecord]] = {
    (BENCHMARK_IMAGE, RECORD_DATASET): ImageBenchmarkDataset,
    (BENCHMARK_IMAGE, RECORD_SUITE): ImageBenchmarkSuite,
    (BENCHMARK_IMAGE, RECORD_RUN): ImageBenchmarkRun,
    (BENCHMARK_VIDEO, RECORD_DATASET): VideoBenchmarkDataset,
    (BENCHMARK_VIDEO, RECORD_SUITE): VideoBenchmarkSuite,
    (BENCHMARK_VIDEO, RECORD_RUN): VideoBenchmarkRun,
}
RECORD_ORDER = (
    (BENCHMARK_IMAGE, RECORD_DATASET),
    (BENCHMARK_IMAGE, RECORD_SUITE),
    (BENCHMARK_IMAGE, RECORD_RUN),
    (BENCHMARK_VIDEO, RECORD_DATASET),
    (BENCHMARK_VIDEO, RECORD_SUITE),
    (BENCHMARK_VIDEO, RECORD_RUN),
)


@dataclass(frozen=True)
class BenchmarkJsonRecord:
    user_id: str
    benchmark_kind: str
    record_kind: str
    record: BenchmarkRecord
    source_path: Path


def _summary_key(benchmark_kind: str, record_kind: str) -> str:
    return f"{benchmark_kind}:{record_kind}"


def iter_benchmark_record_json_files(
    data_root: str | Path,
    *,
    on_error: Optional[Callable[[str, str, str, Path, Exception], None]] = None,
) -> Iterable[BenchmarkJsonRecord]:
    """Yield valid per-user benchmark records from JSON directories."""

    users_dir = Path(data_root) / "users"
    if not users_dir.exists():
        return

    for user_dir in sorted(path for path in users_dir.iterdir() if path.is_dir()):
        for benchmark_kind, record_kind in RECORD_ORDER:
            record_dir = user_dir / RECORD_DIRECTORIES[(benchmark_kind, record_kind)]
            if not record_dir.exists():
                continue
            model = RECORD_MODELS[(benchmark_kind, record_kind)]
            for record_path in sorted(record_dir.glob("*.json")):
                try:
                    with record_path.open("r", encoding="utf-8") as handle:
                        data = json.load(handle)
                    yield BenchmarkJsonRecord(
                        user_id=user_dir.name,
                        benchmark_kind=benchmark_kind,
                        record_kind=record_kind,
                        record=model(**data),
                        source_path=record_path,
                    )
                except Exception as exc:
                    if on_error:
                        on_error(user_dir.name, benchmark_kind, record_kind, record_path, exc)


def backfill_benchmark_records(
    data_root: str | Path,
    repository_factory: RepositoryFactory,
) -> dict:
    """Upsert all valid per-user benchmark JSON records into PostgreSQL."""

    failures: list[dict] = []
    scanned_users: set[str] = set()
    counts_by_kind = {_summary_key(*item): 0 for item in RECORD_ORDER}
    upserted_count = 0

    def record_load_failure(
        user_id: str,
        benchmark_kind: str,
        record_kind: str,
        record_path: Path,
        exc: Exception,
    ) -> None:
        failures.append(
            {
                "user_id": user_id,
                "benchmark_kind": benchmark_kind,
                "record_kind": record_kind,
                "record_file": record_path.name,
                "error": exc.__class__.__name__,
            }
        )

    for item in iter_benchmark_record_json_files(data_root, on_error=record_load_failure):
        scanned_users.add(item.user_id)
        counts_by_kind[_summary_key(item.benchmark_kind, item.record_kind)] += 1
        try:
            repository_factory(item.user_id).save(item.benchmark_kind, item.record_kind, item.record)
            upserted_count += 1
        except Exception as exc:
            failures.append(
                {
                    "user_id": item.user_id,
                    "benchmark_kind": item.benchmark_kind,
                    "record_kind": item.record_kind,
                    "record_id": item.record.id,
                    "error": exc.__class__.__name__,
                }
            )

    json_count = sum(counts_by_kind.values())
    return {
        "domain": "benchmark_records",
        "scanned_users": sorted(scanned_users),
        "json_count": json_count,
        "json_count_by_kind": counts_by_kind,
        "upserted_count": upserted_count,
        "failed_count": len(failures),
        "failures": failures,
        "ok": len(failures) == 0,
    }


def write_backfill_summary(summary: dict, output_path: str | Path) -> Path:
    """Write a sanitized benchmark backfill summary JSON file."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path
