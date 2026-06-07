# R31 Benchmark Records Backfill And Reconcile

2026-06-07 completed local benchmark records backfill/reconcile tooling.

## Scope

- Domain: `benchmark_records`
- Benchmark kinds: `image`, `video`
- Record kinds: `dataset`, `suite`, `run`
- Runtime default remains JSON/file-only.
- No runtime dual-write/read-switch/primary-write is connected in this slice.

## Implementation

- Added `backend/app/services/migration/backfill_benchmark_records.py`.
- Added `backend/app/services/migration/reconcile_benchmark_records.py`.
- Added maintenance scripts:
  - `scripts/postgres_backfill_benchmark_records.py`
  - `scripts/postgres_reconcile_benchmark_records.py`

## Sanitization Boundary

Backfill and reconcile summaries are sanitized. They include counts, ids, record kind, benchmark kind, safe field names, file names for invalid JSON, and exception classes.

They must not include:

- prompts or negative prompts
- provider payloads or canonical request bodies
- request ids or provider task ids
- keys, tokens, passwords, or credentials
- private media URLs
- dataset/suite/case/model names or descriptions

## Safe Compare Fields

- dataset: `updated_at`, `project_id`, `task_kind`, `item_count`
- suite: `updated_at`, `project_id`, `dataset_id`, `task_kind`, `status`
- run: `updated_at`, `project_id`, `dataset_id`, `suite_id`, `task_kind`, `status`, `cell_count`

## Verification

```bash
backend/.venv/bin/pytest backend/tests/test_benchmark_record_migration.py -q
```

Result:

```text
3 passed
```

```bash
backend/.venv/bin/python -m py_compile backend/app/services/migration/backfill_benchmark_records.py backend/app/services/migration/reconcile_benchmark_records.py backend/app/repositories/benchmark_records.py scripts/postgres_backfill_benchmark_records.py scripts/postgres_reconcile_benchmark_records.py
backend/.venv/bin/pytest backend/tests/test_benchmark_record_migration.py backend/tests/test_benchmark_record_repository.py backend/tests/test_benchmark_record_schema.py -q
```

Result:

```text
8 passed
```

```bash
backend/.venv/bin/pytest backend/tests/test_benchmark_record_migration.py backend/tests/test_benchmark_record_repository.py backend/tests/test_benchmark_record_schema.py backend/tests/test_project_entity_migration.py backend/tests/test_media_metadata_migration.py backend/tests/test_project_migration.py backend/tests/test_studio_task_migration.py backend/tests/test_video_studio_task_migration.py -q
```

Result:

```text
23 passed
```

```bash
backend/.venv/bin/pytest backend/tests -q
```

Result:

```text
354 passed
```

## RED Gate

The new migration test failed before implementation because `app.services.migration.backfill_benchmark_records` did not exist.

## Next

- Add benchmark runtime dual-write behind feature flags.
- Add benchmark read-switch + JSON fallback after reconcile gates.
- Add benchmark PostgreSQL primary-write + optional JSON archive mirror.
- Keep server rollout paused until SSH command execution and public health are stable.
