# R39 user/config PostgreSQL primary-write

Date: 2026-06-07

## Scope

- Added `user_config` PostgreSQL primary-write feature flag.
- Register, login user updates, password changes, and per-user config saves can write PostgreSQL as primary when explicitly enabled.
- JSON archive mirror is optional through `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true`.
- User/config read helpers treat primary-write mode as PostgreSQL-preferred to avoid writing PostgreSQL while reading only JSON.
- Default runtime remains JSON/Redis/file-only.

## Files

- `backend/app/repositories/user_config_runtime.py`
- `backend/app/services/user_service.py`
- `backend/app/config.py`
- `backend/tests/test_user_config_primary_write.py`

## Verification

```bash
backend/.venv/bin/pytest backend/tests/test_user_config_primary_write.py -q
# 7 passed

backend/.venv/bin/python -m py_compile backend/app/repositories/user_config_runtime.py backend/app/services/user_service.py backend/app/config.py
# passed

backend/.venv/bin/pytest backend/tests/test_user_config_schema.py backend/tests/test_user_config_repository.py backend/tests/test_user_config_migration.py backend/tests/test_user_config_dual_write.py backend/tests/test_user_config_read_switch.py backend/tests/test_user_config_primary_write.py -q
# 33 passed

backend/.venv/bin/pytest backend/tests -q
# 399 passed
```

## Notes

- PostgreSQL primary failures propagate and do not write JSON, avoiding split-brain during cutover.
- Login password verification can use PostgreSQL in primary mode, but active sessions remain Redis + file fallback.
- Server live migration/backfill/reconcile and staged flag enablement remain pending.
