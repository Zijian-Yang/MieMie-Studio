# R14 Projects Backfill And Reconcile

Date: 2026-06-07

Scope:

- Add local backfill/reconcile tooling for the `projects` domain.
- Keep runtime default as JSON/file-only.
- Keep project names, descriptions and script content out of generated summaries.

Implemented behavior:

- Added `backend/app/services/migration/backfill_projects.py` to scan `backend/data/users/<user_id>/projects/*.json` and upsert valid projects through a per-user repository factory.
- Added `backend/app/services/migration/reconcile_projects.py` to compare JSON primary data with PostgreSQL shadow data.
- Added `scripts/postgres_backfill_projects.py` and `scripts/postgres_reconcile_projects.py`.
- Backfill summaries include counts, user ids, project ids and error classes only.
- Reconcile summaries compare safe derived fields: `updated_at`, `script_shot_count`, `character_count`, `scene_count`, `prop_count`, and `style_count`; they do not include project names, descriptions, script text, model configs, prompt bodies or private URLs.

Verification:

- `backend/.venv/bin/pytest backend/tests/test_project_migration.py -q` -> `3 passed`
- `backend/.venv/bin/pytest backend/tests/test_project_migration.py backend/tests/test_project_repository.py backend/tests/test_project_schema.py -q` -> `10 passed`
- `backend/.venv/bin/pytest backend/tests/test_project_migration.py backend/tests/test_studio_task_migration.py backend/tests/test_video_studio_task_migration.py backend/tests/test_project_repository.py backend/tests/test_studio_task_repository.py backend/tests/test_video_studio_task_repository.py -q` -> `21 passed`
- `backend/.venv/bin/python -m py_compile backend/app/services/migration/backfill_projects.py backend/app/services/migration/reconcile_projects.py scripts/postgres_backfill_projects.py scripts/postgres_reconcile_projects.py` -> passed
- `backend/.venv/bin/pytest backend/tests/test_project_migration.py backend/tests/test_project_repository.py backend/tests/test_project_schema.py backend/tests/test_studio_task_migration.py backend/tests/test_studio_task_dual_write.py backend/tests/test_studio_task_read_switch.py backend/tests/test_studio_task_primary_write.py backend/tests/test_video_studio_task_migration.py backend/tests/test_video_studio_task_dual_write.py backend/tests/test_video_studio_task_read_switch.py backend/tests/test_video_studio_task_primary_write.py backend/tests/test_database_health.py -q` -> `41 passed`
- `docker compose config` -> passed
- `git diff --check` -> passed
- `backend/.venv/bin/pytest backend/tests -q` -> `290 passed`

Pending:

- Add `projects` runtime dual-write.
- Add `projects` read-switch and JSON fallback.
- Add `projects` primary-write and optional JSON archive mirror.
- Complete staging PostgreSQL rollout once SSH/public health evidence is stable again.
