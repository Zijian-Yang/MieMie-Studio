# PostgreSQL R3 Local Schema Evidence

Run date: 2026-06-07

Scope:

- Add Alembic configuration.
- Add `video_studio_tasks` SQLAlchemy metadata.
- Add initial PostgreSQL migration for `video_studio_tasks`.
- Keep business read/write paths unchanged.

## Implemented

- `backend/alembic.ini`
- `backend/app/db/migrations/env.py`
- `backend/app/db/migrations/versions/20260607_0001_video_studio_tasks.py`
- `backend/app/db/schema/__init__.py`
- `backend/app/db/schema/video_studio_tasks.py`
- `backend/tests/test_video_studio_task_schema.py`

## Schema Shape

The first table is intentionally both an indexed task table and a full snapshot holder:

- indexed task columns: `id`, `user_id`, `project_id`, `task_kind`, `task_type`, `provider`, `status`, `submit_state`, `submit_attempt_id`, `created_at`, `updated_at`, `deleted_at`
- JSONB payload columns: `input_assets`, `normalized_params`, `provider_payload_snapshot`, `provider_result_meta`, `task_ids`, `request_ids`, `video_urls`, `raw_task_snapshot`
- UI/provider columns used by list/detail/status paths: `name`, `model_id`, `model`, `prompt`, `negative_prompt`, `selected_video_url`, `thumbnail_url`, `error_message`, `group_count`

`raw_task_snapshot` is included so the next shadow/backfill phase can preserve the complete current Pydantic task model while gradually moving indexed reads to PostgreSQL.

## Indexes

- `idx_video_studio_tasks_user_project_updated` on `(user_id, project_id, updated_at DESC)` where `deleted_at IS NULL`
- `idx_video_studio_tasks_user_status_updated` on `(user_id, status, updated_at DESC)` where `deleted_at IS NULL`
- `idx_video_studio_tasks_submit_attempt` on `(submit_attempt_id)` where `submit_attempt_id IS NOT NULL`

## Verification

- `backend/.venv/bin/pytest backend/tests/test_video_studio_task_schema.py -q`: `3 passed`
- `backend/.venv/bin/pytest backend/tests/test_database_health.py -q`: `3 passed`
- `backend/.venv/bin/pytest backend/tests/test_video_studio_task_schema.py backend/tests/test_database_health.py backend/tests/test_docker_runtime.py -q`: `7 passed`
- `MIEMIE_DATABASE_URL=postgresql+psycopg://miemie:example@postgres:5432/miemie backend/.venv/bin/alembic -c backend/alembic.ini upgrade head --sql`: generated SQL successfully
- `docker compose config`: passed
- `git diff --check`: passed

## Not Yet Verified

- Live `alembic upgrade head` against a PostgreSQL container is pending. Local Docker daemon is not running, and staging SSH/health verification is still unreliable after the R1/R2 server build disconnect.

## Sensitive Data

No raw key, token, PostgreSQL password, or private user data was written to this artifact.
