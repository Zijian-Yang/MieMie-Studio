# R26 Project Entities Runtime Dual-Write

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

- Added `backend/app/repositories/project_entity_runtime.py`.
- Connected `StorageService` project editing entity save/delete paths to PostgreSQL shadow writes:
  - `save_character()` / `delete_character()`
  - `save_scene()` / `delete_scene()`
  - `save_prop()` / `delete_prop()`
  - `save_frame()` / `delete_frame()`
  - `save_video()` / `delete_video()`
  - `save_style()` / `delete_style()`
- Added `backend/tests/test_project_entity_dual_write.py`.

## Runtime Flags

Dual-write is enabled only when:

```bash
MIEMIE_DATABASE_ENABLED=true
MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=project_entities
```

or when global write mode is:

```bash
MIEMIE_DATABASE_WRITE_MODE=dual
# or
MIEMIE_DATABASE_WRITE_MODE=dual_write
```

Shadow write failures are non-fatal by default. Set `MIEMIE_DATABASE_RECONCILE_STRICT=true` to propagate shadow failures during strict migration gates.

## Verification

Commands run on 2026-06-07:

```bash
backend/.venv/bin/pytest backend/tests/test_project_entity_dual_write.py -q
backend/.venv/bin/python -m py_compile backend/app/repositories/project_entity_runtime.py backend/app/services/storage.py backend/app/repositories/project_entities.py
backend/.venv/bin/pytest backend/tests/test_project_entity_schema.py backend/tests/test_project_entity_repository.py backend/tests/test_project_entity_migration.py backend/tests/test_project_entity_dual_write.py backend/tests/test_storage_service.py -q
backend/.venv/bin/pytest backend/tests/test_video_studio_task_dual_write.py backend/tests/test_studio_task_dual_write.py backend/tests/test_project_dual_write.py backend/tests/test_media_metadata_dual_write.py backend/tests/test_project_entity_dual_write.py backend/tests/test_project_entity_migration.py backend/tests/test_project_entity_repository.py -q
backend/.venv/bin/pytest backend/tests -q
```

Result:

- RED gate failed before implementation with missing `project_entity_runtime` module.
- Focused dual-write tests: `4 passed`.
- Project entity/storage target tests: `15 passed`.
- Cross-domain dual-write target tests: `23 passed`.
- Full backend suite: `338 passed`.
- `py_compile` passed.

## Next

- Add project entity read-switch with JSON fallback.
- Then add PostgreSQL primary-write with optional JSON archive mirror.
- Server rollout remains blocked from the current operator path until SSH/public health is reliable.
