# R22 Media Metadata Read-Switch

## Scope

- Domain: `media_metadata`
- Runtime feature flag: `MIEMIE_DATABASE_READ_DOMAINS=media_metadata`
- JSON remains the default read path.
- PostgreSQL reads are enabled only when explicitly configured.
- No server state, Nginx, Cloudflare, provider key, OSS object, or production data was changed in this local slice.

## Changes

- Extended `backend/app/repositories/media_asset_runtime.py` with read feature flags and read repository builders.
- Added PostgreSQL-first read helpers for:
  - gallery image get/list
  - audio item get/list
  - video item get/list
  - text item get/list
- Updated `StorageService` media/text get and list methods to use PostgreSQL when read-switch is enabled.
- Added JSON fallback on PostgreSQL miss, empty list, or read exception when `MIEMIE_DATABASE_JSON_FALLBACK_READ=true`.
- Added `backend/tests/test_media_metadata_read_switch.py`.

## Verification

Commands run on 2026-06-07:

```bash
backend/.venv/bin/pytest backend/tests/test_media_metadata_read_switch.py -q
backend/.venv/bin/pytest backend/tests/test_media_metadata_read_switch.py backend/tests/test_media_metadata_dual_write.py backend/tests/test_media_metadata_migration.py backend/tests/test_media_metadata_schema.py backend/tests/test_media_metadata_repository.py backend/tests/test_storage_service.py -q
backend/.venv/bin/python -m py_compile backend/app/repositories/media_asset_runtime.py backend/app/services/storage.py
docker compose config
backend/.venv/bin/pytest backend/tests/test_media_metadata_read_switch.py backend/tests/test_media_metadata_dual_write.py backend/tests/test_media_metadata_migration.py backend/tests/test_media_metadata_schema.py backend/tests/test_media_metadata_repository.py backend/tests/test_project_migration.py backend/tests/test_studio_task_migration.py backend/tests/test_video_studio_task_migration.py backend/tests/test_project_repository.py backend/tests/test_studio_task_repository.py backend/tests/test_video_studio_task_repository.py backend/tests/test_database_health.py -q
backend/.venv/bin/pytest backend/tests -q
```

Result:

- RED read builder gate failed before implementation with missing `build_media_asset_read_repository`.
- Focused read-switch test: `4 passed`.
- Media metadata target: `20 passed`.
- Wider DB target: `43 passed`.
- Full backend suite: `320 passed`.
- `py_compile` and `docker compose config` passed.

## Next

- Add media metadata PostgreSQL primary-write + JSON archive mirror.
- Re-run media selector frontend smoke after primary-write/read-switch behavior is stable.
- Server rollout remains blocked from the current operator path until SSH/public health is reliable.
