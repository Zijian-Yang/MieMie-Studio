# R117 PostgreSQL Operational Cron Install

## Summary

- Run ID: `r117-postgres-operational-cron-install-20260620`
- Result: `passed`
- Installed file: `/etc/cron.d/miemie-postgres-ops`
- Cron service state: `active`

## Installed Schedule

- Daily `03:15`: run PostgreSQL operational readiness with a fresh backup and restore rehearsal.
- Daily `03:45`: run PostgreSQL backup retention with `RETENTION_DAYS=14` and `MIN_KEEP=3`.

## Notes

The jobs write logs on the server under `logs/postgres-operational-readiness-cron.log` and `logs/postgres-backup-retention-cron.log`. Future follow-up should inspect the first scheduled run and archive its artifact.
