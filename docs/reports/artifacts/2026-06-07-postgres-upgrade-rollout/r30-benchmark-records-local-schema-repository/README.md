# R30 Benchmark Records Local Schema And Repository

2026-06-07 completed the first local PostgreSQL boundary for image/video benchmark records.

## Scope

- Domain: `benchmark_records`
- Benchmark kinds: `image`, `video`
- Record kinds: `dataset`, `suite`, `run`
- Runtime default remains JSON/file-only.
- No StorageService runtime read/write switch is connected in this slice.

## Implementation

- Added `backend/app/db/schema/benchmark_records.py`.
- Added Alembic migration `20260607_0006_benchmark_records`.
- Registered `benchmark_records` in shared SQLAlchemy metadata.
- Added `backend/app/repositories/benchmark_records.py` with:
  - `FileBenchmarkRecordRepository`
  - `PostgresBenchmarkRecordRepository`
  - `benchmark_record_to_row()`
  - `row_to_benchmark_record()`

## Table Shape

`benchmark_records` uses a composite primary key:

```text
(id, benchmark_kind, record_kind)
```

The table stores safe query/index fields plus `raw_record_snapshot` JSONB.

Indexed fields include user, project, benchmark kind, record kind, dataset id, suite id, task kind, status, item count, cell count, and timestamps. Full benchmark payloads remain in `raw_record_snapshot` so later migrations can preserve behavior while gradually extracting stable query fields.

## Sensitive Data Boundary

Benchmark runs may contain prompts, provider payloads, request ids, task ids, output URLs, validation warnings, and model/provider details. This slice stores full snapshots in PostgreSQL, but artifact and future reconcile summaries must not print raw prompts, provider payloads, request ids, task ids, keys, tokens, passwords, or private URLs.

## Verification

```bash
backend/.venv/bin/pytest backend/tests/test_benchmark_record_schema.py backend/tests/test_benchmark_record_repository.py -q
```

Result:

```text
5 passed
```

```bash
backend/.venv/bin/python -m py_compile backend/app/db/schema/benchmark_records.py backend/app/db/migrations/versions/20260607_0006_benchmark_records.py backend/app/repositories/benchmark_records.py
backend/.venv/bin/pytest backend/tests/test_benchmark_record_schema.py backend/tests/test_benchmark_record_repository.py backend/tests/test_project_entity_schema.py backend/tests/test_project_entity_repository.py backend/tests/test_media_metadata_schema.py backend/tests/test_media_metadata_repository.py backend/tests/test_project_schema.py backend/tests/test_project_repository.py backend/tests/test_studio_task_schema.py backend/tests/test_studio_task_repository.py backend/tests/test_video_studio_task_schema.py backend/tests/test_video_studio_task_repository.py -q
```

Result:

```text
42 passed
```

```bash
backend/.venv/bin/pytest backend/tests -q
```

Result:

```text
351 passed
```

## RED Gate

The new tests failed before implementation because `app.db.schema.benchmark_records` and `app.repositories.benchmark_records` did not exist.

## Next

- Add benchmark backfill/reconcile scripts with sanitized summaries.
- Then add runtime dual-write, read-switch, and primary-write gates.
- Keep server rollout paused until SSH command execution and public health are stable.
