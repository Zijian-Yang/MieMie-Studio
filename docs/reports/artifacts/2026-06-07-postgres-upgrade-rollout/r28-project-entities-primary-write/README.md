# R28 Project Entities PostgreSQL Primary Write

2026-06-07 completed local `project_entities` PostgreSQL primary-write and optional JSON archive mirror.

## Scope

- Domain: `project_entities`
- Entity kinds: character, scene, prop, frame, video, style
- Runtime default remains `file-only`.
- PostgreSQL primary writes require explicit flags.
- JSON archive mirror is temporary and optional.

## Runtime Flags

```bash
MIEMIE_DATABASE_ENABLED=true
MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=project_entities
MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false
```

`MIEMIE_DATABASE_WRITE_MODE=postgres`, `postgres_primary`, or `primary` also enables PostgreSQL primary writes.

## Behavior

- `StorageService.save_character()` / `save_scene()` / `save_prop()` / `save_frame()` / `save_video()` / `save_style()` write to PostgreSQL primary only when explicitly enabled.
- Matching delete methods mark rows deleted in PostgreSQL primary mode.
- By default, PostgreSQL primary-write success does not update JSON files.
- `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` keeps a temporary JSON archive mirror after successful PostgreSQL primary writes.
- PostgreSQL primary-write failures propagate and do not write JSON, avoiding split-brain state during cutover.

## Verification

```bash
backend/.venv/bin/pytest backend/tests/test_project_entity_primary_write.py -q
```

Result:

```text
4 passed
```

```bash
backend/.venv/bin/python -m py_compile backend/app/repositories/project_entity_runtime.py backend/app/services/storage.py backend/app/repositories/project_entities.py
backend/.venv/bin/pytest backend/tests/test_project_entity_schema.py backend/tests/test_project_entity_repository.py backend/tests/test_project_entity_migration.py backend/tests/test_project_entity_dual_write.py backend/tests/test_project_entity_read_switch.py backend/tests/test_project_entity_primary_write.py backend/tests/test_storage_service.py -q
```

Result:

```text
23 passed
```

```bash
backend/.venv/bin/pytest backend/tests/test_video_studio_task_primary_write.py backend/tests/test_studio_task_primary_write.py backend/tests/test_project_primary_write.py backend/tests/test_media_metadata_primary_write.py backend/tests/test_project_entity_primary_write.py backend/tests/test_project_entity_read_switch.py backend/tests/test_project_entity_repository.py backend/tests/test_storage_service.py -q
```

Result:

```text
29 passed
```

```bash
backend/.venv/bin/pytest backend/tests -q
```

Result:

```text
346 passed
```

## RED Gate

The new primary-write test failed before implementation because `project_entity_runtime` did not expose `build_project_entity_primary_repository`.

## Next

- Restore staging connectivity, then execute live migration/backfill/reconcile and staged dual-write/read-switch/primary-write rollout.
