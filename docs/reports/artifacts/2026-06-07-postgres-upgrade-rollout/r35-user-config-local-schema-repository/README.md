# R35 user/config local schema and repository boundary

Date: 2026-06-07

## Scope

- Added PostgreSQL schema and Alembic migration for `users` and `user_configs`.
- Added user/config row mapping and PostgreSQL repository boundary.
- Kept runtime behavior unchanged: login, sessions, and per-user config reads/writes still use the existing JSON/Redis paths by default.
- Config row indexes expose only safe flags: `api_region`, `has_dashscope_key`, and `has_oss_config`. Raw keys, passwords, tokens, and private user data must not be written to artifacts.

## Files

- `backend/app/db/schema/user_config.py`
- `backend/app/db/migrations/versions/20260607_0007_user_config.py`
- `backend/app/repositories/user_config.py`
- `backend/tests/test_user_config_schema.py`
- `backend/tests/test_user_config_repository.py`

## Verification

```bash
backend/.venv/bin/pytest backend/tests/test_user_config_schema.py backend/tests/test_user_config_repository.py -q
# 8 passed

backend/.venv/bin/python -m py_compile backend/app/db/schema/user_config.py backend/app/repositories/user_config.py backend/app/db/migrations/versions/20260607_0007_user_config.py
# passed

backend/.venv/bin/pytest backend/tests/test_user_config_schema.py backend/tests/test_user_config_repository.py backend/tests/test_benchmark_record_schema.py backend/tests/test_benchmark_record_repository.py -q
# 13 passed

backend/.venv/bin/pytest backend/tests -q
# 374 passed
```

## Notes

- This step intentionally does not switch `UserService` or `ConfigManager` to PostgreSQL.
- Next user/config step should add backfill and reconcile tooling with sanitized summaries before any runtime write/read flag is introduced.
