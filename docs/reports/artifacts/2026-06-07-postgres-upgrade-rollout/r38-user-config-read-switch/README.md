# R38 user/config read-switch

Date: 2026-06-07

## Scope

- Added `user_config` read-switch feature flag with JSON fallback.
- `UserService.get_user_by_id()` and token user recovery can prefer PostgreSQL when explicitly enabled.
- `ConfigManager.load()` can prefer PostgreSQL for per-user config when a current user context exists.
- Login password verification remains JSON primary in this step to keep the authentication write path conservative.

## Files

- `backend/app/repositories/user_config_runtime.py`
- `backend/app/services/user_service.py`
- `backend/app/config.py`
- `backend/tests/test_user_config_read_switch.py`

## Verification

```bash
backend/.venv/bin/pytest backend/tests/test_user_config_read_switch.py -q
# 7 passed

backend/.venv/bin/python -m py_compile backend/app/repositories/user_config_runtime.py backend/app/services/user_service.py backend/app/config.py
# passed

backend/.venv/bin/pytest backend/tests/test_user_config_schema.py backend/tests/test_user_config_repository.py backend/tests/test_user_config_migration.py backend/tests/test_user_config_dual_write.py backend/tests/test_user_config_read_switch.py -q
# 26 passed

backend/.venv/bin/pytest backend/tests -q
# 392 passed
```

## Notes

- Reads prefer PostgreSQL only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_READ_DOMAINS=user_config` or global read mode is explicitly enabled.
- `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` falls back to JSON on PostgreSQL miss or read error.
- Sessions remain Redis + file fallback and are not moved to PostgreSQL.
