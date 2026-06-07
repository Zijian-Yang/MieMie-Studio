# R37 user/config runtime dual-write

Date: 2026-06-07

## Scope

- Added `user_config` runtime dual-write feature flag.
- User shadow writes run after JSON primary writes for register, login password/last-login updates, and password changes.
- Config shadow writes run after `ConfigManager.save()` when a current user context exists.
- Default runtime remains JSON/Redis/file-only. PostgreSQL writes only run when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=user_config` or global dual write mode is explicitly enabled.

## Files

- `backend/app/repositories/user_config_runtime.py`
- `backend/app/services/user_service.py`
- `backend/app/config.py`
- `backend/tests/test_user_config_dual_write.py`

## Verification

```bash
backend/.venv/bin/pytest backend/tests/test_user_config_dual_write.py -q
# 6 passed

backend/.venv/bin/python -m py_compile backend/app/repositories/user_config_runtime.py backend/app/services/user_service.py backend/app/config.py
# passed

backend/.venv/bin/pytest backend/tests/test_user_config_schema.py backend/tests/test_user_config_repository.py backend/tests/test_user_config_migration.py backend/tests/test_user_config_dual_write.py -q
# 19 passed

backend/.venv/bin/pytest backend/tests -q
# 385 passed
```

## Notes

- Shadow failures are warning-only by default and can be made strict with `MIEMIE_DATABASE_RECONCILE_STRICT=true`.
- Strict failures occur after JSON primary writes, matching the existing migration gate pattern.
- Sessions are intentionally not mirrored to PostgreSQL in this step.
