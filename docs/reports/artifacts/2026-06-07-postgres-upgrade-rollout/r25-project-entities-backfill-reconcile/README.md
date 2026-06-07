# R25 Project Entities Backfill/Reconcile

## Scope

- Domain: `project_entities`
- Entity kinds:
  - `character`
  - `scene`
  - `prop`
  - `frame`
  - `video`
  - `style`
- Runtime default remains file-only.
- No server state, Nginx, Cloudflare, provider key, OSS object, or production data was changed in this local slice.

## Changes

- Added `backend/app/services/migration/backfill_project_entities.py`.
- Added `backend/app/services/migration/reconcile_project_entities.py`.
- Added maintenance scripts:
  - `scripts/postgres_backfill_project_entities.py`
  - `scripts/postgres_reconcile_project_entities.py`
- Extended `ProjectEntityRepository` with `list_all(entity_kind)` so reconcile can detect PostgreSQL-only records.
- Added `backend/tests/test_project_entity_migration.py`.

## Privacy Boundary

Backfill and reconcile summaries are intentionally sanitized. They include users, entity kinds, entity ids, counts, field names, and exception class names only. They do not include entity names, descriptions, prompts, text style bodies, provider payloads, task provider ids, token/key/password values, or private URLs.

## Verification

Commands run on 2026-06-07:

```bash
backend/.venv/bin/pytest backend/tests/test_project_entity_migration.py -q
backend/.venv/bin/pytest backend/tests/test_project_entity_schema.py backend/tests/test_project_entity_repository.py backend/tests/test_project_entity_migration.py -q
backend/.venv/bin/python -m py_compile backend/app/services/migration/backfill_project_entities.py backend/app/services/migration/reconcile_project_entities.py backend/app/repositories/project_entities.py scripts/postgres_backfill_project_entities.py scripts/postgres_reconcile_project_entities.py
backend/.venv/bin/pytest backend/tests/test_project_entity_migration.py backend/tests/test_project_entity_repository.py backend/tests/test_project_entity_schema.py backend/tests/test_project_migration.py backend/tests/test_media_metadata_migration.py backend/tests/test_studio_task_migration.py backend/tests/test_video_studio_task_migration.py -q
backend/.venv/bin/pytest backend/tests -q
```

Result:

- RED import gate failed before implementation with missing `backfill_project_entities` module.
- Focused migration tests: `3 passed`.
- Project entity target tests: `10 passed`.
- Cross-domain migration target tests: `22 passed`.
- Full backend suite: `334 passed`.
- `py_compile` passed.

## Next

- Add project entity runtime dual-write.
- Then add read-switch with JSON fallback.
- Then add PostgreSQL primary-write with optional JSON archive mirror.
- Server rollout remains blocked from the current operator path until SSH/public health is reliable.
