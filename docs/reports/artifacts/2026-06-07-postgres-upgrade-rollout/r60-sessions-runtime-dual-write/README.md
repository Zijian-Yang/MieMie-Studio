# R60 Sessions Runtime Dual Write

Date: 2026-06-17

## Summary

R60 adds an opt-in PostgreSQL shadow write boundary for auth sessions without changing the default runtime path.

- Added `backend/app/repositories/session_runtime.py`.
- `UserService` now shadow-saves sessions after login when sessions dual-write is explicitly enabled.
- `UserService` now shadow-deletes one session on logout and all user sessions on password change.
- Default behavior is unchanged: Redis remains the active session store with file fallback.
- PostgreSQL shadow writes are enabled only when `MIEMIE_DATABASE_ENABLED=true` and either:
  - `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=sessions`, or
  - `MIEMIE_DATABASE_WRITE_MODE=dual` / `dual_write`
- Shadow failures are warning-only by default and propagate only with `MIEMIE_DATABASE_RECONCILE_STRICT=true`.
- Runtime logs avoid raw token values.

## Verification

- `backend/.venv/bin/pytest backend/tests/test_session_runtime_dual_write.py -q` -> 5 passed
- `backend/.venv/bin/pytest backend/tests/test_fixes.py backend/tests/test_user_config_dual_write.py backend/tests/test_user_config_read_switch.py backend/tests/test_user_config_primary_write.py backend/tests/test_session_repository.py backend/tests/test_session_schema.py backend/tests/test_session_migration.py backend/tests/test_session_runtime_dual_write.py -q` -> 63 passed
- `backend/.venv/bin/pytest backend/tests/test_*schema.py backend/tests/test_*repository.py backend/tests/test_*migration.py backend/tests/test_session_runtime_dual_write.py -q` -> 87 passed
- `backend/.venv/bin/pytest backend/tests -q` -> 413 passed
- `python3 -m py_compile backend/app/repositories/session_runtime.py backend/app/services/user_service.py` -> passed

## Server State

No server command was executed in this step, and no database business flag was enabled on staging.

The local operator path remains blocked by the R59 connectivity evidence:

- `../r59-connectivity-after-direct-rule/status.json`
- `../r59-connectivity-after-direct-rule/remediation.md`
