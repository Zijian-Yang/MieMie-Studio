# R15 Projects Runtime Dual Write

Date: 2026-06-07

Scope:

- Add feature-flagged PostgreSQL shadow writes for `projects`.
- Keep runtime default as JSON/file-only.
- Preserve existing project public API behavior and storage order.

Implemented behavior:

- Added `backend/app/repositories/project_runtime.py`.
- `projects` dual-write is disabled by default.
- When `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=projects` or `MIEMIE_DATABASE_WRITE_MODE=dual/dual_write`, `StorageService.save_project()` writes JSON primary first, then shadow-saves PostgreSQL.
- `StorageService.delete_project()` deletes JSON first, then shadow-marks the PostgreSQL project deleted.
- Non-strict PostgreSQL shadow failures are logged and do not interrupt the JSON primary path.
- Strict mode can propagate shadow failures through `MIEMIE_DATABASE_RECONCILE_STRICT=true`.

Verification:

- `backend/.venv/bin/pytest backend/tests/test_project_dual_write.py -q` -> `3 passed`
- `backend/.venv/bin/pytest backend/tests/test_project_dual_write.py backend/tests/test_project_migration.py backend/tests/test_project_repository.py backend/tests/test_project_schema.py backend/tests/test_storage_service.py -q` -> `14 passed`
- `backend/.venv/bin/python -m py_compile backend/app/repositories/project_runtime.py backend/app/services/storage.py` -> passed
- `backend/.venv/bin/pytest backend/tests/test_project_dual_write.py backend/tests/test_studio_task_dual_write.py backend/tests/test_video_studio_task_dual_write.py backend/tests/test_project_migration.py backend/tests/test_studio_task_migration.py backend/tests/test_video_studio_task_migration.py -q` -> `18 passed`
- `backend/.venv/bin/pytest backend/tests/test_project_dual_write.py backend/tests/test_project_migration.py backend/tests/test_project_repository.py backend/tests/test_project_schema.py backend/tests/test_studio_task_dual_write.py backend/tests/test_studio_task_read_switch.py backend/tests/test_studio_task_primary_write.py backend/tests/test_studio_task_migration.py backend/tests/test_video_studio_task_dual_write.py backend/tests/test_video_studio_task_read_switch.py backend/tests/test_video_studio_task_primary_write.py backend/tests/test_video_studio_task_migration.py backend/tests/test_database_health.py -q` -> `44 passed`
- `docker compose config` -> passed
- `git diff --check` -> passed
- `backend/.venv/bin/pytest backend/tests -q` -> `293 passed`

Pending:

- Add `projects` read-switch and JSON fallback.
- Add `projects` primary-write and optional JSON archive mirror.
- Complete staging PostgreSQL rollout once SSH/public health evidence is stable again.
