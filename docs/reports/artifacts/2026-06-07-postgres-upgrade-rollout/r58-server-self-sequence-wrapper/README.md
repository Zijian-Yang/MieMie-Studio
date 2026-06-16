# R58 Server Self Sequence Wrapper

## Summary

- Run ID: `r58-server-self-sequence-wrapper-20260617`
- State: `dry_run`
- Server state changed: no
- Database business flags changed: no

This artifact records the local dry-run contract for `scripts/pre_studio_server_postgres_sequence.sh`.

The wrapper is a server-terminal fallback for cases where the operator Mac cannot SSH cleanly because local DNS/route still go through Clash fake-IP/TUN. It is meant to be run inside the server repository, usually `/opt/miemie-pre`.

## Server Command

Run this on the server from `/opt/miemie-pre` after pulling this commit:

```bash
CONFIRM_SERVER_SEQUENCE=run scripts/pre_studio_server_postgres_sequence.sh
```

Default behavior is dry-run only. The script requires `CONFIRM_SERVER_SEQUENCE=run` before it will:

- verify it is on branch `pre`;
- confirm `compose.env`, `docker-compose.yml`, `docker-compose.pre.override.yml`, and the staging sequence runner exist;
- perform `git fetch origin pre` plus `git merge --ff-only origin/pre`;
- execute `CONFIRM_STAGING_SEQUENCE=run scripts/postgres_staging_video_task_sequence.sh`.

## Evidence

- `status.json`
- `commands.log`
- `server-sequence-plan.sh`

## Notes

The checked-in artifact is a local dry-run, so its generated `cd` path reflects the local workspace. A server dry-run or confirmed run will generate the same plan shape with the server repository path.
