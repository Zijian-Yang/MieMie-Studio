# R6 Runtime Dual-Write Feature Flag

## Scope

This artifact records the local runtime dual-write feature flag for `video_studio_tasks`.

Implemented:

- `backend/app/repositories/video_studio_task_runtime.py`
  - checks `MIEMIE_DATABASE_ENABLED`.
  - enables shadow writes when `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS` contains `video_studio_tasks` or `MIEMIE_DATABASE_WRITE_MODE=dual`.
  - lazily creates a PostgreSQL engine only after dual-write is enabled.
  - logs PostgreSQL shadow write/delete failures without breaking JSON primary unless `MIEMIE_DATABASE_RECONCILE_STRICT=true`.
- `backend/app/services/storage.py`
  - keeps JSON writes/deletes as the primary path.
  - adds `owner_user_id` for user-specific `StorageService` instances so background workers created through `get_user_storage(user_id)` can shadow-write with the correct user id.
  - shadow-saves video studio tasks after JSON write succeeds.
  - shadow-marks video studio tasks deleted after JSON delete is attempted.
- `backend/tests/test_video_studio_task_dual_write.py`
  - default file-only behavior.
  - enabled save/delete shadow calls.
  - PostgreSQL shadow failure does not break JSON primary.

Not changed:

- Reads still use JSON/file storage.
- Runtime dual-write remains disabled by default.
- No staging dual-write was enabled in this slice.
- No public API response shape was changed.

## Verification

```text
backend/.venv/bin/pytest backend/tests/test_video_studio_task_dual_write.py -q
3 passed in 0.67s

backend/.venv/bin/pytest backend/tests/test_video_studio_task_dual_write.py backend/tests/test_video_studio_task_repository.py backend/tests/test_video_studio_task_migration.py backend/tests/test_video_studio_task_schema.py backend/tests/test_database_health.py backend/tests/test_storage_service.py -q
17 passed in 0.74s

git diff --check
passed

backend/.venv/bin/pytest backend/tests -q
251 passed in 64.11s
```

## Follow-Up

- Recover staging SSH/API verification.
- Run live `alembic upgrade head`.
- Run live backfill and reconcile.
- Enable `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=video_studio_tasks` on staging only after reconcile is clean.
- Create a disposable task through the public API and reconcile again.
- Proceed to read switch only after dual-write evidence is clean.
