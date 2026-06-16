# R59 Sessions Local Schema Repository

Date: 2026-06-17

## Summary

R59 adds the local PostgreSQL migration foundation for `sessions.json` without changing runtime session behavior.

- Added `sessions` PostgreSQL schema and Alembic revision `20260607_0008`.
- Added a session repository boundary that stores only `token_hash`, never raw session tokens.
- Added sanitized `sessions.json` backfill and reconcile helpers plus maintenance scripts.
- Added `sessions` to `scripts/postgres_live_rehearsal.sh` so the local/live rehearsal path includes the new domain after user/config.
- Kept runtime unchanged: current auth sessions still use Redis with file fallback unless a later stage introduces a dedicated session read/write switch.

## Verification

- `backend/.venv/bin/pytest backend/tests/test_session_repository.py backend/tests/test_session_schema.py backend/tests/test_session_migration.py -q` -> 9 passed
- `backend/.venv/bin/pytest backend/tests/test_session_repository.py backend/tests/test_session_schema.py backend/tests/test_session_migration.py backend/tests/test_user_config_repository.py backend/tests/test_user_config_schema.py backend/tests/test_user_config_migration.py -q` -> 22 passed
- `backend/.venv/bin/pytest backend/tests/test_*schema.py backend/tests/test_*repository.py backend/tests/test_*migration.py -q` -> 82 passed
- `backend/.venv/bin/pytest backend/tests/test_fixes.py backend/tests/test_user_config_read_switch.py backend/tests/test_user_config_primary_write.py backend/tests/test_session_repository.py backend/tests/test_session_schema.py backend/tests/test_session_migration.py -q` -> 52 passed
- `backend/.venv/bin/pytest backend/tests -q` -> 408 passed
- `python3 -m py_compile ...sessions...` -> passed
- `bash -n scripts/postgres_live_rehearsal.sh scripts/postgres_backup.sh scripts/postgres_restore_rehearsal.sh` -> passed
- `MIEMIE_DATABASE_URL=postgresql+psycopg://miemie:local-dev-password@localhost:5432/miemie backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head --sql` -> passed, includes `20260607_0008`

## Server Connectivity

After the latest local Clash DIRECT rule update, full connectivity preflight is still blocked from this Mac.

See:

- `../r59-connectivity-after-direct-rule/status.json`
- `../r59-connectivity-after-direct-rule/results.tsv`
- `../r59-connectivity-after-direct-rule/remediation.md`

The remote PostgreSQL sequence was not executed in this step.
