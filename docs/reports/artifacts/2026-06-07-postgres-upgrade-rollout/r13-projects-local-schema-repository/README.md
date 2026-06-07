# R13 Projects Local Schema And Repository

Date: 2026-06-07

Scope:

- Add the first PostgreSQL boundary for `projects`.
- Keep runtime default as JSON/file-only.
- Do not migrate child resources or enable read/write switching in this slice.

Implemented behavior:

- Added `projects` SQLAlchemy schema with indexed columns for `user_id`, `name`, `updated_at`, child-count summaries, `llm_configs`, and full `raw_project_snapshot`.
- Added Alembic migration `20260607_0003_projects` after `20260607_0002_studio_tasks`.
- Added `ProjectRepository` protocol plus file/PostgreSQL/dual repository implementations.
- PostgreSQL repository uses soft delete through `deleted_at`; file repository preserves existing `StorageService` JSON behavior.
- Dual repository writes JSON primary first, then shadows PostgreSQL; non-strict shadow failures do not interrupt JSON primary writes.

Verification:

- `backend/.venv/bin/pytest backend/tests/test_project_schema.py backend/tests/test_project_repository.py -q` -> `7 passed`
- `backend/.venv/bin/pytest backend/tests/test_project_schema.py backend/tests/test_project_repository.py backend/tests/test_studio_task_schema.py backend/tests/test_studio_task_repository.py backend/tests/test_studio_task_migration.py backend/tests/test_studio_task_dual_write.py backend/tests/test_studio_task_read_switch.py backend/tests/test_studio_task_primary_write.py backend/tests/test_video_studio_task_schema.py backend/tests/test_video_studio_task_repository.py backend/tests/test_video_studio_task_migration.py backend/tests/test_video_studio_task_dual_write.py backend/tests/test_video_studio_task_read_switch.py backend/tests/test_video_studio_task_primary_write.py backend/tests/test_database_health.py -q` -> `52 passed`
- `backend/.venv/bin/python -m py_compile backend/app/db/schema/projects.py backend/app/repositories/projects.py backend/app/db/migrations/versions/20260607_0003_projects.py` -> passed
- `MIEMIE_DATABASE_URL=postgresql+psycopg://miemie:example@postgres:5432/miemie backend/.venv/bin/alembic -c backend/alembic.ini upgrade head --sql` -> generated SQL through `20260607_0003`
- `docker compose config` -> passed
- `git diff --check` -> passed
- `backend/.venv/bin/pytest backend/tests -q` -> `287 passed`

Pending:

- Add `projects` backfill/reconcile tooling.
- Add `projects` runtime dual-write, read-switch and primary-write gates after backfill/reconcile.
- Complete staging PostgreSQL rollout once SSH/public health evidence is stable again.
