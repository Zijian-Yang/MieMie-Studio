# R21 Media Metadata Runtime Dual-Write

## Scope

- Domain: `media_metadata`
- Runtime feature flag: `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=media_metadata`
- JSON remains primary.
- PostgreSQL writes are shadow writes only.
- No server state, Nginx, Cloudflare, provider key, OSS object, or production data was changed in this local slice.

## Changes

- Added `backend/app/repositories/media_asset_runtime.py`.
- Added explicit runtime helpers for gallery, audio library, video library, and text library shadow writes/deletes.
- Updated `StorageService` save/delete paths:
  - JSON file write/delete happens first.
  - PostgreSQL shadow write/delete runs only when database is enabled and dual-write is explicitly enabled for `media_metadata`.
  - Shadow failures are logged and do not break JSON primary unless `MIEMIE_DATABASE_RECONCILE_STRICT=true`.
- Added `backend/tests/test_media_metadata_dual_write.py`.

## Verification

Commands run on 2026-06-07:

```bash
backend/.venv/bin/pytest backend/tests/test_media_metadata_dual_write.py -q
backend/.venv/bin/pytest backend/tests/test_media_metadata_dual_write.py backend/tests/test_media_metadata_migration.py backend/tests/test_media_metadata_schema.py backend/tests/test_media_metadata_repository.py backend/tests/test_storage_service.py -q
backend/.venv/bin/python -m py_compile backend/app/repositories/media_asset_runtime.py backend/app/services/storage.py
docker compose config
backend/.venv/bin/pytest backend/tests/test_media_metadata_dual_write.py backend/tests/test_media_metadata_migration.py backend/tests/test_media_metadata_schema.py backend/tests/test_media_metadata_repository.py backend/tests/test_project_migration.py backend/tests/test_studio_task_migration.py backend/tests/test_video_studio_task_migration.py backend/tests/test_project_repository.py backend/tests/test_studio_task_repository.py backend/tests/test_video_studio_task_repository.py backend/tests/test_database_health.py -q
backend/.venv/bin/pytest backend/tests -q
```

Result:

- RED runtime import gate failed before implementation with `ModuleNotFoundError`.
- Focused dual-write test: `3 passed`.
- Media metadata target: `16 passed`.
- Wider DB target: `39 passed`.
- Full backend suite: `316 passed`.
- `py_compile` and `docker compose config` passed.

## Next

- Add media metadata PostgreSQL read-switch with JSON fallback for gallery/audio/video/text library list and get paths.
- After read-switch gates pass, add PostgreSQL primary-write + JSON archive mirror.
- Re-run frontend smoke that covers media selectors after read-switch changes.
