# R64 Staging Live Data Gate

Date: 2026-06-17

## Summary

R64 adds a reusable server-side live data gate before application-level PostgreSQL canaries.

- New script: `scripts/postgres_staging_live_data_gate.sh`.
- Default mode is dry-run and only writes a redacted execution plan.
- Explicit run mode executes Alembic `upgrade head`, then all current domain backfill/reconcile scripts, then PostgreSQL backup and restore rehearsal.
- Maintenance database flags are injected only for the script process; the script does not switch application runtime read/write flags.
- Raw maintenance env and PostgreSQL dumps stay under `/tmp` and are not written to committed artifacts.
- Domains covered: `video_studio_tasks`, `studio_tasks`, `projects`, `media_metadata`, `project_entities`, `benchmark_records`, `user_config`, `sessions`.

## Verification

- RED: `python3 scripts/verify_postgres_staging_canary_sequence.py` failed before implementation because the sequence did not include `live-data-gate`.
- RED: `python3 scripts/verify_postgres_staging_live_data_gate.py` failed before implementation because `scripts/postgres_staging_live_data_gate.sh` did not exist.
- `python3 scripts/verify_postgres_staging_live_data_gate.py` -> passed.
- `python3 scripts/verify_postgres_staging_canary_sequence.py` -> passed.
- `python3 -m py_compile scripts/verify_postgres_staging_live_data_gate.py scripts/verify_postgres_staging_canary_sequence.py` -> passed.
- Local dry-run wrote `status.json`, `domains.txt`, and `live-data-gate-plan.sh`.

## Server State

No server sequence was executed in R64.

The local operator route to `47.79.99.190` still used `utun1024` via `198.18.0.1`; TCP 22 succeeded, but SSH timed out during banner exchange. Server runtime and database business switches were not modified.
