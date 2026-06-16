# R64 Staging Sequence With Live Data Gate

Date: 2026-06-17

## Summary

R64 updates the staging PostgreSQL sequence runner so app-level canaries run only after live data gates pass.

Default sequence:

```text
audit
roll-runtime
live-data-gate
dual-write-canary
read-switch-canary
rollback-read-switch
primary-write-canary
rollback-primary-write
```

The `live-data-gate` stage calls `scripts/postgres_staging_live_data_gate.sh` with `CONFIRM_LIVE_DATA_GATE=run`. Existing app-level stages continue to call `scripts/postgres_staging_video_task_canary.sh`.

## Verification

- `python3 scripts/verify_postgres_staging_canary_sequence.py` -> passed.
- Local dry-run wrote `sequence.txt`, `results.tsv`, and `status.json` without executing Docker, SSH, or child canary scripts.

## Server State

No server command was executed by this dry-run artifact.
