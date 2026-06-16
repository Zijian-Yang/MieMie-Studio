# R66 Remote Wrapper Server Fallback Alignment

Date: 2026-06-17

## Summary

R66 aligns the local remote PostgreSQL wrapper with the server-terminal fallback.

- `scripts/pre_studio_remote_postgres_sequence.sh` still runs the local connectivity preflight before any SSH command.
- The generated remote command still performs `git fetch origin pre` and `git merge --ff-only origin/pre`.
- After sync, the remote command now calls `CONFIRM_SERVER_SEQUENCE=run SERVER_SYNC=none scripts/pre_studio_server_postgres_sequence.sh`.
- This reuses the server-side checks added in R65, including the `live-data-gate` contract.

## Verification

- RED: `python3 scripts/verify_pre_studio_remote_postgres_sequence.py` failed before implementation because the remote command did not call `CONFIRM_SERVER_SEQUENCE=run`.
- `python3 scripts/verify_pre_studio_remote_postgres_sequence.py` -> passed.
- `bash -n scripts/pre_studio_remote_postgres_sequence.sh` -> passed.
- Dry-run artifact wrote `remote-command.sh` and `status.json`.

## Server State

No server command was executed by this artifact.
