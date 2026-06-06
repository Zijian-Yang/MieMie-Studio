# R5 Backfill And Reconcile

## Scope

This artifact records the local R5 implementation for `video_studio_tasks`.

Implemented:

- `backend/app/services/migration/backfill_video_studio_tasks.py`
  - scans `backend/data/users/<user_id>/video_studio/*.json`.
  - upserts valid tasks through a per-user repository factory.
  - writes sanitized JSON summaries without prompt bodies, provider payloads, tokens, keys, passwords, or private URLs.
- `backend/app/services/migration/reconcile_video_studio_tasks.py`
  - compares JSON and PostgreSQL repository state for scanned users.
  - checks counts, ids, `project_id`, `status`, `updated_at`, and `submit_attempt_id`.
  - renders sanitized JSON and Markdown summaries.
- `scripts/postgres_backfill_video_studio_tasks.py`
- `scripts/postgres_reconcile_video_studio_tasks.py`

Not changed:

- Runtime routes and workers still do not read from PostgreSQL.
- No live backfill/reconcile was executed against staging PostgreSQL in this slice.
- JSON remains the primary production data path.

## Verification

```text
backend/.venv/bin/pytest backend/tests/test_video_studio_task_migration.py -q
3 passed in 0.89s

backend/.venv/bin/pytest backend/tests/test_video_studio_task_migration.py backend/tests/test_video_studio_task_repository.py backend/tests/test_video_studio_task_schema.py backend/tests/test_database_health.py -q
13 passed in 0.79s

python3 -m py_compile scripts/postgres_backfill_video_studio_tasks.py scripts/postgres_reconcile_video_studio_tasks.py
passed

scripts/postgres_backfill_video_studio_tasks.py --help
scripts/postgres_reconcile_video_studio_tasks.py --help
passed

git diff --check
passed

backend/.venv/bin/pytest backend/tests -q
248 passed in 63.83s
```

## Follow-Up

- Recover staging SSH/API verification and close R1/R2.
- Run live `alembic upgrade head` after PostgreSQL container health is proven.
- Run:

```bash
python3 scripts/postgres_backfill_video_studio_tasks.py
python3 scripts/postgres_reconcile_video_studio_tasks.py
```

inside the staging app path after `MIEMIE_DATABASE_URL` is configured and the migration table exists.
