# R6 Read Switch And JSON Fallback

## Scope

This artifact records the local read-switch implementation for `video_studio_tasks`.

Implemented:

- `backend/app/repositories/video_studio_task_runtime.py`
  - `video_studio_task_read_enabled()`
  - `json_fallback_read_enabled()`
  - PostgreSQL-first `get`, project list, and all-task list helpers.
  - JSON fallback on PostgreSQL miss/error when `MIEMIE_DATABASE_JSON_FALLBACK_READ=true`.
- `backend/app/services/storage.py`
  - keeps private JSON read helpers.
  - routes `get_video_studio_task()`, `get_video_studio_tasks()`, and `get_all_video_studio_tasks()` through the read-switch helper.
- `backend/tests/test_video_studio_task_read_switch.py`
  - default file-only reads.
  - PostgreSQL-first get/list reads.
  - JSON fallback on PostgreSQL miss.
  - fallback-disabled error propagation.

Not changed:

- Runtime read switch remains disabled by default.
- No staging read switch was enabled in this slice.
- Public API response shapes remain unchanged because the returned object is still `VideoStudioTask`.
- PostgreSQL primary mode and JSON archive mode are still future phases.

## Verification

```text
backend/.venv/bin/pytest backend/tests/test_video_studio_task_read_switch.py -q
4 passed in 0.82s

backend/.venv/bin/pytest backend/tests/test_video_studio_task_read_switch.py backend/tests/test_video_studio_task_dual_write.py backend/tests/test_video_studio_task_repository.py backend/tests/test_video_studio_task_migration.py backend/tests/test_video_studio_task_schema.py backend/tests/test_database_health.py backend/tests/test_storage_service.py backend/tests/test_video_studio_capabilities.py -q
78 passed in 9.60s

git diff --check
passed

backend/.venv/bin/pytest backend/tests -q
255 passed in 65.30s
```

## Follow-Up

- Recover staging SSH/API verification.
- Run live migration, backfill, reconcile, and dual-write smoke first.
- Enable `MIEMIE_DATABASE_READ_DOMAINS=video_studio_tasks` on staging only after reconcile is clean.
- Roll back reads with `MIEMIE_DATABASE_READ_DOMAINS=` and keep `MIEMIE_DATABASE_WRITE_MODE=file`.
- Re-run status/list gates through both local Nginx entry and public Cloudflare entry.
