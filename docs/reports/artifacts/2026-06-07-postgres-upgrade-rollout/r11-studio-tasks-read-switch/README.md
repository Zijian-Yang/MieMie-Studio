# R11 Studio Tasks Read Switch

Date: 2026-06-07

Scope:

- Add feature-flagged PostgreSQL read switch for image studio tasks.
- Keep runtime default as JSON/file-only.
- Preserve public API response shapes and JSON fallback during migration.

Implemented behavior:

- `studio_tasks` reads stay file-only by default.
- When `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_READ_DOMAINS=studio_tasks` or `MIEMIE_DATABASE_READ_MODE=postgres`, `StorageService.get_studio_task()` and `get_studio_tasks_by_project()` prefer PostgreSQL.
- If `MIEMIE_DATABASE_JSON_FALLBACK_READ=true`, PostgreSQL misses or read errors fall back to JSON.
- If `MIEMIE_DATABASE_JSON_FALLBACK_READ=false`, PostgreSQL read errors propagate to support strict gates.

Verification:

- `backend/.venv/bin/pytest backend/tests/test_studio_task_read_switch.py -q` -> `4 passed`
- `backend/.venv/bin/pytest backend/tests/test_studio_task_read_switch.py backend/tests/test_studio_task_dual_write.py backend/tests/test_studio_task_migration.py backend/tests/test_studio_task_repository.py backend/tests/test_studio_task_schema.py backend/tests/test_video_studio_task_read_switch.py backend/tests/test_video_studio_task_dual_write.py backend/tests/test_video_studio_task_primary_write.py backend/tests/test_storage_service.py backend/tests/test_studio_capabilities.py -q` -> `83 passed`
- `backend/.venv/bin/python -m py_compile backend/app/repositories/studio_task_runtime.py` -> passed
- `git diff --check` -> passed
- `docker compose config >/tmp/miemie-compose-config-check.txt` -> passed
- `backend/.venv/bin/pytest backend/tests -q` -> `276 passed`

Pending:

- Add `studio_tasks` PostgreSQL primary-write mode and optional JSON archive mirror.
- Complete staging PostgreSQL rollout once SSH/public health evidence is available again.
