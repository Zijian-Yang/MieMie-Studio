# R27 Project Entities Read-Switch

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

- Extended `backend/app/repositories/project_entity_runtime.py` with read feature flags, read repository builder, JSON fallback helpers, and project/kind filtered lookup helpers.
- Connected `StorageService` project editing entity read paths to PostgreSQL-first reads:
  - single get: character, scene, prop, frame, video, style
  - project lists: character, scene, prop, frame, video, style
  - filtered lookups: frame by shot, video by shot, video by provider task id
- Added `backend/tests/test_project_entity_read_switch.py`.

## Runtime Flags

Read-switch is enabled only when:

```bash
MIEMIE_DATABASE_ENABLED=true
MIEMIE_DATABASE_READ_DOMAINS=project_entities
```

or when global read mode is:

```bash
MIEMIE_DATABASE_READ_MODE=postgres
```

When `MIEMIE_DATABASE_JSON_FALLBACK_READ=true`, PostgreSQL miss, empty project list, or read error falls back to JSON. When fallback is false, PostgreSQL read errors propagate for strict migration gates.

## Verification

Commands run on 2026-06-07:

```bash
backend/.venv/bin/pytest backend/tests/test_project_entity_read_switch.py -q
backend/.venv/bin/python -m py_compile backend/app/repositories/project_entity_runtime.py backend/app/services/storage.py backend/app/repositories/project_entities.py
backend/.venv/bin/pytest backend/tests/test_project_entity_schema.py backend/tests/test_project_entity_repository.py backend/tests/test_project_entity_migration.py backend/tests/test_project_entity_dual_write.py backend/tests/test_project_entity_read_switch.py backend/tests/test_storage_service.py -q
backend/.venv/bin/pytest backend/tests/test_video_studio_task_read_switch.py backend/tests/test_studio_task_read_switch.py backend/tests/test_project_read_switch.py backend/tests/test_media_metadata_read_switch.py backend/tests/test_project_entity_read_switch.py backend/tests/test_project_entity_repository.py -q
backend/.venv/bin/pytest backend/tests -q
```

Result:

- RED gate failed before implementation with missing `build_project_entity_read_repository`.
- Focused read-switch tests: `4 passed`.
- Project entity/storage target tests: `19 passed`.
- Cross-domain read-switch target tests: `24 passed`.
- Full backend suite: `342 passed`.
- `py_compile` passed.

## Next

- Add project entity PostgreSQL primary-write with optional JSON archive mirror.
- Then run frontend/project editing smoke for this domain once runtime flags are ready.
- Server rollout remains blocked from the current operator path until SSH/public health is reliable.
