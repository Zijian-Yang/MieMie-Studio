# R61 Sessions Read Switch

Date: 2026-06-17

## Summary

R61 adds an opt-in PostgreSQL read switch for auth sessions without changing the default runtime path.

- `session_runtime.py` now exposes `session_read_enabled()` and `read_session()`.
- `UserService.get_user_by_token()` can prefer PostgreSQL sessions when explicitly enabled.
- Reads prefer PostgreSQL only when `MIEMIE_DATABASE_ENABLED=true` and either:
  - `MIEMIE_DATABASE_READ_DOMAINS=sessions`, or
  - `MIEMIE_DATABASE_READ_MODE=postgres`
- `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` falls back to the current Redis/file session path on PostgreSQL miss or read error.
- Default behavior remains unchanged: Redis/file remains the active auth session path.
- This step does not add sessions primary-write and does not enable any staging database business flag.

## Verification

- RED: `backend/.venv/bin/pytest backend/tests/test_session_runtime_read_switch.py -q` failed before implementation because `build_session_read_repository` did not exist.
- `backend/.venv/bin/pytest backend/tests/test_session_runtime_read_switch.py -q` -> 4 passed
- `backend/.venv/bin/pytest backend/tests/test_session_runtime_read_switch.py backend/tests/test_session_runtime_dual_write.py backend/tests/test_session_repository.py backend/tests/test_session_schema.py backend/tests/test_session_migration.py -q` -> 18 passed
- `backend/.venv/bin/pytest backend/tests/test_fixes.py backend/tests/test_user_config_dual_write.py backend/tests/test_user_config_read_switch.py backend/tests/test_user_config_primary_write.py backend/tests/test_session_repository.py backend/tests/test_session_schema.py backend/tests/test_session_migration.py backend/tests/test_session_runtime_dual_write.py backend/tests/test_session_runtime_read_switch.py -q` -> 67 passed
- `backend/.venv/bin/pytest backend/tests/test_*schema.py backend/tests/test_*repository.py backend/tests/test_*migration.py backend/tests/test_session_runtime_dual_write.py backend/tests/test_session_runtime_read_switch.py -q` -> 91 passed
- `python3 -m py_compile backend/app/repositories/session_runtime.py backend/app/services/user_service.py backend/tests/test_session_runtime_read_switch.py` -> passed

## Server State

No server command was executed in this step, and no database business flag was enabled on staging.
