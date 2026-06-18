# R88 User Account Runtime Coverage

R88 closes a remaining PostgreSQL-only runtime gap in the account identity path.

Before this change, `UserService.list_user_ids()` still enumerated root `backend/data/users.json` even when `user_config` reads or PostgreSQL primary mode were enabled. That path is used by video task startup recovery, so final JSON exit could still depend on the root account JSON file.

The change adds a `user_config_runtime.list_user_ids()` read helper and routes `UserService.list_user_ids()` through it. File-only mode still returns JSON IDs. PostgreSQL read/primary mode now lists users from `PostgresUserRepository.list_all()`, with JSON fallback only when `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` and the PostgreSQL list operation fails.

## Verification

```bash
cd backend && .venv/bin/python -m pytest tests/test_user_config_read_switch.py -q
cd backend && .venv/bin/python -m pytest tests/test_user_config_read_switch.py tests/test_user_config_primary_write.py tests/test_user_config_dual_write.py -q
```

Observed:

- `8 passed`
- `21 passed`

No server rollout, container restart, database switch, token, password, or private user data was involved in this local runtime coverage patch.
