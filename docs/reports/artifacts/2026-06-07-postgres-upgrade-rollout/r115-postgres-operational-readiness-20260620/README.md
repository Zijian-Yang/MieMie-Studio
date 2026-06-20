# R115 PostgreSQL Operational Readiness

## Summary

- Run ID: `r115-postgres-operational-readiness-20260620`
- Result: `passed`
- Checks: `24 passed`, `0 warn`, `0 blocked`, `0 failed`
- Runtime server repo head during run: `43410b6ff0a734604e12875532711cb16af4f414`

## Covered Gate

- Final PostgreSQL-only env policy stayed intact.
- Local and public `/api/health` passed with `database.ok=true` and `redis.ok=true`.
- Compose ps and `docker stats --no-stream` were captured.
- Remaining JSON outside quarantine was exactly `backend/data/config.example.json`.
- A new PostgreSQL backup was created at `backend/backups/postgres/miemie-postgres-20260620-150733.sql`.
- Restore rehearsal passed against an isolated check database.

## Repository Safety

The SQL dump remains on the server under `backend/backups/postgres/`. This artifact stores only summaries, sanitized env, health headers/bodies, Docker state, and the backup path.
