# R10 Studio Tasks Runtime Dual Write

Date: 2026-06-07

Scope:

- Add feature-flagged PostgreSQL shadow writes for image studio tasks.
- Keep JSON as the runtime primary store.
- Do not change read paths, public API response shapes, or server deployment flags.

Implemented behavior:

- Added `backend/app/repositories/studio_task_runtime.py`.
- `StorageService.save_studio_task()` writes JSON first, then shadow-saves PostgreSQL only when enabled.
- `StorageService.delete_studio_task()` deletes JSON first, then shadow-marks PostgreSQL deleted only when enabled.
- Enablement requires `MIEMIE_DATABASE_ENABLED=true` plus either:
  - `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=studio_tasks`, or
  - `MIEMIE_DATABASE_WRITE_MODE=dual` / `dual_write`.
- `MIEMIE_DATABASE_RECONCILE_STRICT=false` keeps PostgreSQL shadow failures from breaking JSON primary writes.
- `MIEMIE_DATABASE_RECONCILE_STRICT=true` propagates shadow failures for stricter gates.

Verification:

- `backend/.venv/bin/pytest backend/tests/test_studio_task_dual_write.py -q` -> `3 passed`
- `backend/.venv/bin/pytest backend/tests/test_studio_task_dual_write.py backend/tests/test_studio_task_migration.py backend/tests/test_studio_task_repository.py backend/tests/test_studio_task_schema.py backend/tests/test_video_studio_task_dual_write.py backend/tests/test_video_studio_task_read_switch.py backend/tests/test_video_studio_task_primary_write.py backend/tests/test_storage_service.py backend/tests/test_studio_capabilities.py -q` -> `79 passed`
- `backend/.venv/bin/python -m py_compile backend/app/repositories/studio_task_runtime.py` -> passed
- `git diff --check` -> passed
- `docker compose config >/tmp/miemie-compose-config-check.txt` -> passed
- `backend/.venv/bin/pytest backend/tests -q` -> `272 passed`

Pending:

- Add `studio_tasks` read switch and JSON fallback.
- Add `studio_tasks` PostgreSQL primary-write mode and optional JSON archive mirror.
- Complete staging PostgreSQL rollout once SSH/public health evidence is available again.
