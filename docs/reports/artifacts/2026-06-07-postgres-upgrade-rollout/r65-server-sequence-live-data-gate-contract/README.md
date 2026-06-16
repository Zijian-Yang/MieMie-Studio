# R65 Server Sequence Live Data Gate Contract

Date: 2026-06-17

## Summary

R65 tightens the server-side PostgreSQL sequence fallback before live execution.

- `scripts/pre_studio_server_postgres_sequence.sh` dry-run plan now checks that `scripts/postgres_staging_video_task_sequence.sh` contains `live-data-gate`.
- The plan also checks that `scripts/postgres_staging_live_data_gate.sh` exists.
- Run mode verifies the same contract before and after `git merge --ff-only origin/pre`.

## Verification

- `python3 scripts/verify_pre_studio_server_postgres_sequence.py` -> passed.
- Dry-run artifact wrote `server-sequence-plan.sh` and `status.json`.

## Server State

No server command was executed by this artifact.
