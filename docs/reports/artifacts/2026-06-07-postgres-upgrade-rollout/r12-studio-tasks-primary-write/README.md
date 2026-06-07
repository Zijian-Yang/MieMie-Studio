# R12 Studio Tasks Primary Write

Date: 2026-06-07

Scope:

- Add feature-flagged PostgreSQL primary-write mode for image studio tasks.
- Keep runtime default as JSON/file-only.
- Add optional JSON archive mirror for temporary audit/recovery during cutover.
- Preserve public API response shapes and existing JSON behavior unless explicit database flags are enabled.

Implemented behavior:

- `studio_tasks` writes stay file-only by default.
- When `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=studio_tasks` or `MIEMIE_DATABASE_WRITE_MODE=postgres/postgres_primary/primary`, `StorageService.save_studio_task()` and `delete_studio_task()` write/delete through PostgreSQL primary.
- When PostgreSQL primary-write succeeds and `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true`, StorageService also maintains a temporary JSON archive mirror.
- PostgreSQL primary-write failures propagate and do not write JSON, avoiding split-brain states where PostgreSQL failed but JSON appears successful.

Verification:

- `backend/.venv/bin/pytest backend/tests/test_studio_task_primary_write.py -q` -> `4 passed`
- `backend/.venv/bin/pytest backend/tests/test_studio_task_primary_write.py backend/tests/test_studio_task_read_switch.py backend/tests/test_studio_task_dual_write.py backend/tests/test_studio_task_migration.py backend/tests/test_studio_task_repository.py backend/tests/test_studio_task_schema.py backend/tests/test_video_studio_task_primary_write.py backend/tests/test_storage_service.py backend/tests/test_studio_capabilities.py -q` -> `80 passed`
- `backend/.venv/bin/python -m py_compile backend/app/repositories/studio_task_runtime.py` -> passed
- `git diff --check` -> passed
- `docker compose config` -> passed
- `backend/.venv/bin/pytest backend/tests -q` -> `280 passed`

Pending:

- Complete staging PostgreSQL container health, live migration, backfill and reconcile once SSH/public health evidence is stable again.
- Enable staging dual-write, read-switch and primary-write gradually, with JSON archive mirror only during cutover/audit.
- Continue the next local domain migration, likely `projects`, if staging access remains blocked.
