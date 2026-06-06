# R6 PostgreSQL Primary Write

Date: 2026-06-07

Scope:

- Implement local `video_studio_tasks` PostgreSQL primary-write mode.
- Keep runtime default as file-only unless PostgreSQL primary-write flags are explicitly enabled.
- Add optional JSON archive mirror for audit/recovery windows.
- Do not claim staging primary-write enablement; live migration/backfill/reconcile/read-switch gates are still pending.

Implemented behavior:

- `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=video_studio_tasks` enables PostgreSQL primary writes for video studio task saves/deletes when `MIEMIE_DATABASE_ENABLED=true`.
- `MIEMIE_DATABASE_WRITE_MODE=postgres_primary` is also accepted for primary-write mode.
- `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` keeps a JSON mirror after successful PostgreSQL primary writes.
- PostgreSQL primary-write failures propagate and do not write JSON, preventing split-brain state.
- Save paths refresh `updated_at` before PostgreSQL/file writes so repository ordering and reconcile fields remain meaningful.

Verification:

- `backend/.venv/bin/pytest backend/tests/test_video_studio_task_primary_write.py -q` -> `4 passed`
- `backend/.venv/bin/pytest backend/tests/test_video_studio_task_primary_write.py backend/tests/test_video_studio_task_read_switch.py backend/tests/test_video_studio_task_dual_write.py backend/tests/test_video_studio_task_repository.py backend/tests/test_video_studio_task_migration.py backend/tests/test_video_studio_task_schema.py backend/tests/test_database_health.py backend/tests/test_storage_service.py backend/tests/test_video_studio_capabilities.py -q` -> `82 passed`
- `git diff --check` -> passed
- `backend/.venv/bin/pytest backend/tests -q` -> `259 passed`
- `docker compose config >/tmp/miemie-compose-config-check.txt` -> passed

Next gate:

- Resume staging rollout from PostgreSQL container/health verification before enabling live migration or primary-write flags.
