# R48 Local Live Database Rehearsal Passed

2026-06-17 fixed the local rehearsal backup discovery and reran the full Compose PostgreSQL live rehearsal.

## Result

- `scripts/postgres_live_rehearsal.sh`: passed.
- Temporary PostgreSQL started and was removed with `docker compose down -v`.
- `alembic upgrade head`: passed.
- All domain backfill scripts: passed.
- All domain reconcile scripts: `ok=true`.
- `scripts/postgres_backup.sh`: created a `.sql` backup.
- `scripts/postgres_restore_rehearsal.sh`: restored the backup into `miemie_restore_check`, ran `select 1`, and dropped the temporary restore database.
- Post-run Docker check found no `miemie-postgres-rehearsal` container remnants.

## Sanitized Counts

See `sanitized-summary.json`. Raw per-domain backfill/reconcile outputs were intentionally not committed because local development data includes user UUIDs. The committed summary keeps counts and pass/fail state only.

## Remaining Server Work

This proves the local all-domain live database rehearsal gate. It does not switch staging application traffic. Staging still needs the R45 server sequence after SSH command execution is stable:

1. `MODE=audit scripts/postgres_staging_video_task_canary.sh`
2. `MODE=roll-runtime scripts/postgres_staging_video_task_canary.sh`
3. `MODE=dual-write-canary scripts/postgres_staging_video_task_canary.sh`
