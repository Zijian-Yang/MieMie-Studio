# R36 user/config backfill and reconcile

Date: 2026-06-07

## Scope

- Added user/config JSON backfill service and script.
- Added user/config PostgreSQL reconcile service and script.
- Reconcile summaries compare only safe fields and counts. They do not output password hashes, raw keys, tokens, complete config snapshots, or private user data.
- Runtime remains unchanged: `UserService`, sessions, and `ConfigManager` still use existing JSON/Redis/file paths by default.

## Files

- `backend/app/services/migration/backfill_user_config.py`
- `backend/app/services/migration/reconcile_user_config.py`
- `scripts/postgres_backfill_user_config.py`
- `scripts/postgres_reconcile_user_config.py`
- `backend/tests/test_user_config_migration.py`

## Verification

```bash
backend/.venv/bin/pytest backend/tests/test_user_config_migration.py -q
# 5 passed

backend/.venv/bin/python -m py_compile backend/app/services/migration/backfill_user_config.py backend/app/services/migration/reconcile_user_config.py scripts/postgres_backfill_user_config.py scripts/postgres_reconcile_user_config.py backend/app/repositories/user_config.py
# passed

backend/.venv/bin/pytest backend/tests/test_user_config_schema.py backend/tests/test_user_config_repository.py backend/tests/test_user_config_migration.py -q
# 13 passed

backend/.venv/bin/pytest backend/tests -q
# 379 passed
```

## Notes

- Backfill reads `users.json` and optional `users/{user_id}/config.json`.
- `sessions.json` is intentionally not migrated in this step; active sessions remain Redis + file fallback.
- Next step should add explicit runtime write flags for user/config only after live migration and sanitized reconcile are green.
