"""Reconcile JSON and PostgreSQL benchmark record state."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.repositories.benchmark_records import RECORD_RUN, BenchmarkRecord
from app.services.migration.backfill_benchmark_records import (
    RECORD_ORDER,
    RepositoryFactory,
    iter_benchmark_record_json_files,
)


SAFE_COMPARE_FIELDS = {
    "dataset": ("updated_at", "project_id", "task_kind", "item_count"),
    "suite": ("updated_at", "project_id", "dataset_id", "task_kind", "status"),
    "run": ("updated_at", "project_id", "dataset_id", "suite_id", "task_kind", "status", "cell_count"),
}


def _safe_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _status(record: BenchmarkRecord) -> str | None:
    value = getattr(record, "status", None)
    return getattr(value, "value", value)


def _safe_projection(record_kind: str, record: BenchmarkRecord) -> dict[str, Any]:
    projection = {
        "updated_at": _safe_value(record.updated_at),
        "project_id": record.project_id,
        "dataset_id": getattr(record, "dataset_id", None),
        "suite_id": getattr(record, "suite_id", None),
        "task_kind": record.task_kind,
        "status": _status(record),
        "item_count": len(getattr(record, "items", []) or []),
        "cell_count": len(getattr(record, "cell_results", []) or []),
    }
    return {
        field: projection[field]
        for field in SAFE_COMPARE_FIELDS[record_kind]
    }


def _record_key(benchmark_kind: str, record_kind: str, record_id: str) -> tuple[str, str, str]:
    return benchmark_kind, record_kind, record_id


def reconcile_benchmark_records(
    data_root: str | Path,
    repository_factory: RepositoryFactory,
) -> dict:
    """Compare JSON primary benchmark records with PostgreSQL shadow data."""

    json_by_user: dict[str, dict[tuple[str, str, str], BenchmarkRecord]] = {}
    load_failures: list[dict] = []

    def record_load_failure(
        user_id: str,
        benchmark_kind: str,
        record_kind: str,
        record_path: Path,
        exc: Exception,
    ) -> None:
        load_failures.append(
            {
                "user_id": user_id,
                "benchmark_kind": benchmark_kind,
                "record_kind": record_kind,
                "record_file": record_path.name,
                "error": exc.__class__.__name__,
            }
        )

    for item in iter_benchmark_record_json_files(data_root, on_error=record_load_failure):
        json_by_user.setdefault(item.user_id, {})
        json_by_user[item.user_id][_record_key(item.benchmark_kind, item.record_kind, item.record.id)] = item.record

    missing_in_postgres: list[dict] = []
    missing_in_json: list[dict] = []
    field_differences: list[dict] = []
    postgres_count_by_kind = {f"{benchmark_kind}:{record_kind}": 0 for benchmark_kind, record_kind in RECORD_ORDER}

    for user_id in sorted(json_by_user):
        repository = repository_factory(user_id)
        project_ids = {
            record.project_id
            for record in json_by_user[user_id].values()
        }
        postgres_items: dict[tuple[str, str, str], BenchmarkRecord] = {}
        for benchmark_kind, record_kind in RECORD_ORDER:
            records: list[BenchmarkRecord] = []
            for project_id in sorted(project_ids):
                records.extend(repository.list_for_project(benchmark_kind, record_kind, project_id))
            postgres_count_by_kind[f"{benchmark_kind}:{record_kind}"] += len(records)
            for record in records:
                postgres_items[_record_key(benchmark_kind, record_kind, record.id)] = record

        json_items = json_by_user[user_id]
        for benchmark_kind, record_kind, record_id in sorted(set(json_items) - set(postgres_items)):
            missing_in_postgres.append(
                {
                    "user_id": user_id,
                    "benchmark_kind": benchmark_kind,
                    "record_kind": record_kind,
                    "record_id": record_id,
                }
            )

        for benchmark_kind, record_kind, record_id in sorted(set(postgres_items) - set(json_items)):
            missing_in_json.append(
                {
                    "user_id": user_id,
                    "benchmark_kind": benchmark_kind,
                    "record_kind": record_kind,
                    "record_id": record_id,
                }
            )

        for key in sorted(set(json_items) & set(postgres_items)):
            benchmark_kind, record_kind, record_id = key
            json_projection = _safe_projection(record_kind, json_items[key])
            postgres_projection = _safe_projection(record_kind, postgres_items[key])
            for field in SAFE_COMPARE_FIELDS[record_kind]:
                if json_projection[field] != postgres_projection[field]:
                    field_differences.append(
                        {
                            "user_id": user_id,
                            "benchmark_kind": benchmark_kind,
                            "record_kind": record_kind,
                            "record_id": record_id,
                            "field": field,
                        }
                    )

    json_count_by_kind = {f"{benchmark_kind}:{record_kind}": 0 for benchmark_kind, record_kind in RECORD_ORDER}
    for records in json_by_user.values():
        for benchmark_kind, record_kind, _ in records:
            json_count_by_kind[f"{benchmark_kind}:{record_kind}"] += 1

    summary = {
        "domain": "benchmark_records",
        "json_count": sum(json_count_by_kind.values()),
        "postgres_count": sum(postgres_count_by_kind.values()),
        "json_count_by_kind": json_count_by_kind,
        "postgres_count_by_kind": postgres_count_by_kind,
        "missing_in_postgres": missing_in_postgres,
        "missing_in_json": missing_in_json,
        "field_differences": field_differences,
        "load_failures": load_failures,
    }
    summary["ok"] = not (
        missing_in_postgres
        or missing_in_json
        or field_differences
        or load_failures
    )
    return summary


def render_reconcile_markdown(summary: dict) -> str:
    """Render a sanitized human-readable benchmark reconcile summary."""

    lines = [
        "# Benchmark Records Reconcile",
        "",
        f"- domain: `{summary['domain']}`",
        f"- ok: `{str(summary['ok']).lower()}`",
        f"- json_count: `{summary['json_count']}`",
        f"- postgres_count: `{summary['postgres_count']}`",
        f"- missing_in_postgres: `{len(summary['missing_in_postgres'])}`",
        f"- missing_in_json: `{len(summary['missing_in_json'])}`",
        f"- field_differences: `{len(summary['field_differences'])}`",
        f"- load_failures: `{len(summary.get('load_failures', []))}`",
        "",
    ]

    for key in ("missing_in_postgres", "missing_in_json", "field_differences", "load_failures"):
        items = summary.get(key, [])
        if not items:
            continue
        lines.append(f"## {key}")
        for item in items:
            prefix = (
                f"user_id=`{item['user_id']}` benchmark_kind=`{item['benchmark_kind']}` "
                f"record_kind=`{item['record_kind']}`"
            )
            if key == "field_differences":
                lines.append(
                    f"- {prefix} record_id=`{item['record_id']}` field=`{item['field']}`"
                )
            elif key == "load_failures":
                lines.append(
                    f"- {prefix} record_file=`{item['record_file']}` error=`{item['error']}`"
                )
            else:
                lines.append(
                    f"- {prefix} record_id=`{item['record_id']}`"
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_reconcile_reports(summary: dict, output_dir: str | Path) -> tuple[Path, Path]:
    """Write sanitized JSON and Markdown reconcile summaries."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "benchmark_records_reconcile.json"
    markdown_path = output_path / "benchmark_records_reconcile.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    markdown_path.write_text(render_reconcile_markdown(summary), encoding="utf-8")
    return json_path, markdown_path
