# R9 Studio Tasks Backfill And Reconcile

Date: 2026-06-07

Scope:

- Continue the `studio_tasks` PostgreSQL migration path after local schema/repository setup.
- Add local JSON backfill and reconciliation tooling for image studio tasks.
- Keep runtime behavior unchanged: image studio tasks remain JSON/file-only until explicit runtime feature flags are added and gated.

Implemented behavior:

- `backend/app/services/migration/backfill_studio_tasks.py`
  - scans `backend/data/users/<user_id>/studio/*.json`
  - validates each JSON file as `StudioTask`
  - upserts each valid task through a per-user repository factory
  - returns a sanitized summary that excludes prompt bodies, provider payloads, tokens, keys, and private URLs
- `backend/app/services/migration/reconcile_studio_tasks.py`
  - compares JSON primary data with PostgreSQL shadow data per user
  - checks safe fields only: `project_id`, `status`, `updated_at`, `last_task_id`
  - writes sanitized JSON and Markdown summaries
- `scripts/postgres_backfill_studio_tasks.py`
- `scripts/postgres_reconcile_studio_tasks.py`

Verification:

- `backend/.venv/bin/pytest backend/tests/test_studio_task_migration.py -q` -> `3 passed`
- `backend/.venv/bin/python -m py_compile scripts/postgres_backfill_studio_tasks.py scripts/postgres_reconcile_studio_tasks.py backend/app/services/migration/backfill_studio_tasks.py backend/app/services/migration/reconcile_studio_tasks.py` -> passed
- `backend/.venv/bin/pytest backend/tests/test_studio_task_migration.py backend/tests/test_studio_task_repository.py backend/tests/test_studio_task_schema.py backend/tests/test_video_studio_task_migration.py backend/tests/test_video_studio_task_repository.py backend/tests/test_video_studio_task_schema.py backend/tests/test_database_health.py -q` -> `23 passed`
- `git diff --check` -> passed
- `backend/.venv/bin/pytest backend/tests -q` -> `269 passed`

Pending:

- Add `studio_tasks` runtime dual-write feature flag.
- Add `studio_tasks` read switch and JSON fallback.
- Add `studio_tasks` PostgreSQL primary-write mode and optional JSON archive mirror.
- Complete staging PostgreSQL rollout once SSH/public health evidence is available again.
