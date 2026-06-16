# R63 Sessions Primary Write

Date: 2026-06-17

## Summary

R63 adds an opt-in PostgreSQL primary-write path for auth sessions without changing the default runtime behavior.

- `session_runtime.py` now exposes `session_primary_write_enabled()`, `json_archive_writes_enabled()`, and primary save/delete helpers.
- `UserService._save_session()` writes PostgreSQL first only when `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=sessions` or a global PostgreSQL write mode is enabled.
- Redis remains a hot session cache after a successful PostgreSQL primary save.
- `sessions.json` is not written by default in session primary-write mode.
- `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` keeps a temporary `sessions.json` archive mirror during cutover windows.
- PostgreSQL primary failures propagate and do not write Redis/file fallback state, avoiding split-brain session state.
- Session primary-write also implies PostgreSQL reads so token recovery works without a separate read-domain flag.
- Default runtime remains Redis/file with optional dual-write/read-switch only when explicitly enabled.

## Verification

- RED: `backend/.venv/bin/pytest backend/tests/test_session_runtime_primary_write.py -q` failed before implementation because `build_session_primary_repository` did not exist.
- Focused: `backend/.venv/bin/pytest backend/tests/test_session_runtime_primary_write.py -q` -> `7 passed`.
- Sessions runtime combined: `backend/.venv/bin/pytest backend/tests/test_session_runtime_primary_write.py backend/tests/test_session_runtime_read_switch.py backend/tests/test_session_runtime_dual_write.py backend/tests/test_session_repository.py backend/tests/test_session_schema.py backend/tests/test_session_migration.py -q` -> `25 passed`.
- Auth/session target: `backend/.venv/bin/pytest backend/tests/test_fixes.py backend/tests/test_user_config_dual_write.py backend/tests/test_user_config_read_switch.py backend/tests/test_user_config_primary_write.py backend/tests/test_session_repository.py backend/tests/test_session_schema.py backend/tests/test_session_migration.py backend/tests/test_session_runtime_dual_write.py backend/tests/test_session_runtime_read_switch.py backend/tests/test_session_runtime_primary_write.py -q` -> `74 passed`.
- Database schema/repository/migration target: `backend/.venv/bin/pytest backend/tests/test_*schema.py backend/tests/test_*repository.py backend/tests/test_*migration.py backend/tests/test_session_runtime_dual_write.py backend/tests/test_session_runtime_read_switch.py backend/tests/test_session_runtime_primary_write.py -q` -> `98 passed`.
- Full backend: `backend/.venv/bin/pytest backend/tests -q` -> `424 passed`.
- `python3 -m py_compile backend/app/repositories/session_runtime.py backend/app/services/user_service.py backend/tests/test_session_runtime_primary_write.py` -> passed.

## Server State

No server command was executed in R63.

No container restart, database business switch, or staging sequence was run.
