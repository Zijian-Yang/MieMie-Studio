# R53 Remote PostgreSQL Sequence Wrapper

2026-06-17 added a local wrapper for the remote PostgreSQL staging sequence. It connects the R52 connectivity preflight to the R51 server-side sequence runner, so database feature flags are not touched unless the operator path is healthy first.

## New Script

Added `scripts/pre_studio_remote_postgres_sequence.sh`.

Default behavior is dry-run:

```bash
scripts/pre_studio_remote_postgres_sequence.sh
```

Execution requires:

```bash
CONFIRM_REMOTE_SEQUENCE=run scripts/pre_studio_remote_postgres_sequence.sh
```

When confirmed, the wrapper:

1. Runs `scripts/pre_studio_connectivity_preflight.sh` locally.
2. Stops locally if the preflight exits non-zero.
3. SSHes to `root@47.79.99.190` only after preflight passes.
4. Changes to `/opt/miemie-pre`.
5. Runs `git fetch origin pre` and `git merge --ff-only origin/pre`.
6. Runs `CONFIRM_STAGING_SEQUENCE=run scripts/postgres_staging_video_task_sequence.sh`.
7. Optionally pulls remote artifacts back from `/opt/miemie-pre/validation-artifacts/<run_id>`.

The wrapper deliberately avoids destructive sync commands such as `git reset --hard`.

## Current Live Result

The confirmed wrapper path was run once outside the sandbox. It stopped at the local preflight stage and did not SSH into the server sequence:

- wrapper state: `blocked`
- wrapper stage: `preflight`
- reason: `local connectivity preflight exited with 2`
- preflight DNS: `198.18.0.80`, fake-IP detected
- preflight route: gateway `198.18.0.1`, interface `utun1024`
- TCP 22: passed
- SSH banner: timed out during banner exchange
- public health: timed out after 20 seconds with no bytes received

No server command, container restart, database switch, or provider call was executed.

## Verification

- `bash -n scripts/pre_studio_remote_postgres_sequence.sh`: passed.
- `python3 scripts/verify_pre_studio_remote_postgres_sequence.py`: passed.
- `python3 scripts/verify_pre_studio_connectivity_preflight.py`: passed.
- `python3 scripts/verify_postgres_staging_canary_sequence.py`: passed.
- Dry-run wrote the expected remote command and did not execute network commands.
- Confirmed run stopped at local preflight while the route remained blocked.

## Next Gate

Once `scripts/pre_studio_connectivity_preflight.sh` exits `0`, rerun:

```bash
CONFIRM_REMOTE_SEQUENCE=run scripts/pre_studio_remote_postgres_sequence.sh
```

This will sync the server repo with `git merge --ff-only origin/pre` and execute the R51 sequence.
