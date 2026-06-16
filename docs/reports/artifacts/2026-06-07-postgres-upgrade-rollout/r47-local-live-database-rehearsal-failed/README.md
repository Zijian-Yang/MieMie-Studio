# R47 Local Live Database Rehearsal Failed

2026-06-17 reran `scripts/postgres_live_rehearsal.sh` after Docker daemon access was confirmed outside the sandbox.

## Result

- `docker info`: available outside the sandbox.
- Temporary PostgreSQL started.
- `alembic upgrade head`: passed.
- All domain backfill scripts: passed.
- All domain reconcile scripts: `ok=true`.
- `scripts/postgres_backup.sh`: created a `.sql` backup.
- `scripts/postgres_live_rehearsal.sh`: failed at backup discovery because it searched for `*.dump`.

## Root Cause

The rehearsal script expected `*.dump`, but `scripts/postgres_backup.sh` intentionally writes `miemie-postgres-<timestamp>.sql`, matching the restore script usage contract.

## Security

Raw command logs and per-domain outputs from this local run were intentionally not committed because they include local-only user UUIDs. This artifact keeps the failure mode and root cause only.
