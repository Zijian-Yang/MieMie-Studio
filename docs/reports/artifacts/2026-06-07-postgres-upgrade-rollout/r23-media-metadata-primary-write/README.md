# R23 Media Metadata PostgreSQL Primary Write

## Scope

- Domain: `media_metadata`
- Runtime feature flag: `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=media_metadata`
- Runtime default remains file-only.
- JSON archive mirror is optional and controlled by `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true`.
- No server state, Nginx, Cloudflare, provider key, OSS object, or production data was changed in this local slice.

## Changes

- Extended `backend/app/repositories/media_asset_runtime.py` with primary-write flags and primary repository builders.
- Added PostgreSQL-primary save/delete helpers for:
  - gallery images
  - audio library items
  - video library items
  - text library items
- Updated `StorageService` media/text save and delete paths:
  - primary-write mode writes PostgreSQL first.
  - JSON is not written unless JSON archive mirror is explicitly enabled.
  - primary-write failure propagates and does not write JSON, avoiding split-brain.
- Added `backend/tests/test_media_metadata_primary_write.py`.

## Verification

Commands run on 2026-06-07:

```bash
backend/.venv/bin/pytest backend/tests/test_media_metadata_primary_write.py -q
backend/.venv/bin/pytest backend/tests/test_media_metadata_primary_write.py backend/tests/test_media_metadata_read_switch.py backend/tests/test_media_metadata_dual_write.py backend/tests/test_media_metadata_migration.py backend/tests/test_media_metadata_schema.py backend/tests/test_media_metadata_repository.py backend/tests/test_storage_service.py -q
backend/.venv/bin/python -m py_compile backend/app/repositories/media_asset_runtime.py backend/app/services/storage.py
docker compose config
backend/.venv/bin/pytest backend/tests/test_media_metadata_primary_write.py backend/tests/test_media_metadata_read_switch.py backend/tests/test_media_metadata_dual_write.py backend/tests/test_media_metadata_migration.py backend/tests/test_media_metadata_schema.py backend/tests/test_media_metadata_repository.py backend/tests/test_project_migration.py backend/tests/test_studio_task_migration.py backend/tests/test_video_studio_task_migration.py backend/tests/test_project_repository.py backend/tests/test_studio_task_repository.py backend/tests/test_video_studio_task_repository.py backend/tests/test_database_health.py -q
backend/.venv/bin/pytest backend/tests -q
```

Result:

- RED primary builder gate failed before implementation with missing `build_media_asset_primary_repository`.
- Focused primary-write test: `4 passed`.
- Media metadata target: `24 passed`.
- Wider DB target: `47 passed`.
- Full backend suite: `324 passed`.
- `py_compile` and `docker compose config` passed.

## Next

- Re-run frontend smoke for media selector flows after a dedicated browser/dev-server setup.
- Server rollout remains blocked from the current operator path until SSH/public health is reliable.
- After server access is restored, run live migration, live backfill/reconcile, staging dual-write, staging read-switch, staging primary-write, and rollback gates.
