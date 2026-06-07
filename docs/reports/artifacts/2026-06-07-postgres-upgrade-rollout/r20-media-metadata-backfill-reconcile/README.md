# R20 Media Metadata Backfill/Reconcile

## Scope

- Domain: `media_metadata`
- Tables: `media_assets`, `text_items`
- JSON sources:
  - gallery images
  - audio library items
  - video library items
  - text library items
- Runtime mode remains file-only by default.
- No server state, Nginx, Cloudflare, provider key, OSS object, or production data was changed in this local slice.

## Changes

- Added local backfill service for media metadata JSON files into PostgreSQL repositories.
- Added local reconcile service that compares JSON and PostgreSQL counts, ids, and safe indexed fields.
- Added maintenance scripts:
  - `scripts/postgres_backfill_media_metadata.py`
  - `scripts/postgres_reconcile_media_metadata.py`
- Added tests for scan, backfill summary, and sanitized reconcile reports.

## Sanitization

Reconcile reports intentionally compare only safe fields:

- gallery: `updated_at`
- audio: `updated_at`, `file_size`, `duration`
- video library: `updated_at`, `file_size`, `duration`, `width`, `height`, `fps`
- text library: `updated_at`, `version_count`

Summary files must not include raw prompt/body content, provider payloads, token/key/password values, text contents, or private URLs.

## Verification

Commands run on 2026-06-07:

```bash
backend/.venv/bin/pytest backend/tests/test_media_metadata_migration.py -q
backend/.venv/bin/pytest backend/tests/test_media_metadata_migration.py backend/tests/test_media_metadata_schema.py backend/tests/test_media_metadata_repository.py backend/tests/test_storage_service.py -q
backend/.venv/bin/python -m py_compile backend/app/services/migration/backfill_media_metadata.py backend/app/services/migration/reconcile_media_metadata.py backend/app/repositories/media_assets.py scripts/postgres_backfill_media_metadata.py scripts/postgres_reconcile_media_metadata.py
git diff --check
backend/.venv/bin/pytest backend/tests/test_media_metadata_migration.py backend/tests/test_media_metadata_schema.py backend/tests/test_media_metadata_repository.py backend/tests/test_project_migration.py backend/tests/test_studio_task_migration.py backend/tests/test_video_studio_task_migration.py backend/tests/test_project_repository.py backend/tests/test_studio_task_repository.py backend/tests/test_video_studio_task_repository.py backend/tests/test_database_health.py -q
docker compose config
backend/.venv/bin/pytest backend/tests -q
```

Result:

- RED import gate failed before implementation with `ModuleNotFoundError`, then passed after implementation.
- Focused migration test: `3 passed`.
- Media metadata target: `13 passed`.
- Wider DB target: `36 passed`.
- Full backend suite: `313 passed`.
- `py_compile`, `git diff --check`, and `docker compose config` passed.

## Next

- Add runtime dual-write for media metadata with JSON primary and PostgreSQL shadow writes.
- Add PostgreSQL read-switch + JSON fallback for media/listing paths.
- Add PostgreSQL primary-write + JSON archive mirror after reconcile gates.
- Re-run relevant frontend smoke after read-switch touches asset selectors.
