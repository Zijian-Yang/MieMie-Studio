# R8 Studio Tasks Local Schema And Repository

Date: 2026-06-07

Scope:

- Continue the database upgrade while staging SSH/public health is blocked by the operator-side TUN/fake-ip path.
- Add the next local domain foundation for `studio_tasks`, matching the existing `video_studio_tasks` migration pattern.
- Do not change runtime reads/writes yet; image studio tasks remain JSON/file-only until backfill/reconcile/dual-write/read-switch gates are added.

Implemented behavior:

- Added `backend/app/db/schema/studio_tasks.py`.
- Added Alembic migration `20260607_0002_studio_tasks`, chained after `20260607_0001`.
- Added `StudioTaskRepository` protocol.
- Added file/PostgreSQL/dual repositories for image studio tasks.
- PostgreSQL rows store indexed task fields plus `raw_task_snapshot` JSONB for lossless transitional migration.
- Partial indexes cover active per-user project lists and status scans:
  - `(user_id, project_id, updated_at desc) where deleted_at is null`
  - `(user_id, status, updated_at desc) where deleted_at is null`

Verification:

- `backend/.venv/bin/pytest backend/tests/test_studio_task_schema.py backend/tests/test_studio_task_repository.py -q` -> `7 passed`
- `backend/.venv/bin/pytest backend/tests/test_studio_task_schema.py backend/tests/test_studio_task_repository.py backend/tests/test_video_studio_task_schema.py backend/tests/test_video_studio_task_repository.py backend/tests/test_video_studio_task_migration.py backend/tests/test_video_studio_task_dual_write.py backend/tests/test_video_studio_task_read_switch.py backend/tests/test_video_studio_task_primary_write.py backend/tests/test_database_health.py backend/tests/test_storage_service.py backend/tests/test_studio_capabilities.py -q` -> `86 passed`
- `backend/.venv/bin/python -m py_compile backend/app/db/migrations/versions/20260607_0002_studio_tasks.py` -> passed
- `MIEMIE_DATABASE_URL=postgresql+psycopg://miemie:example@localhost:5432/miemie backend/.venv/bin/alembic -c backend/alembic.ini heads` -> `20260607_0002 (head)`
- `docker compose config >/tmp/miemie-compose-config-check.txt` -> passed
- `git diff --check` -> passed
- `backend/.venv/bin/pytest backend/tests -q` -> `266 passed`

Pending:

- Add `studio_tasks` backfill/reconcile scripts.
- Add runtime feature flags for image studio task dual-write/read-switch/primary-write.
- Complete staging PostgreSQL rollout once SSH/public health evidence is available again.
