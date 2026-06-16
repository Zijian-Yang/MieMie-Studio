# R51 Staging Sequence Runner And Connectivity

2026-06-17 continued the PostgreSQL staging rollout from R50. The server execution path is still blocked before remote command execution, so this slice adds a safer sequence runner and records current connectivity evidence.

## Connectivity Check

Commands were run from the current local operator path:

- `ssh -o BatchMode=yes -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new root@47.79.99.190 'echo ok; hostname; date -Is'`
  - Result: failed before remote command execution.
  - Error: `Connection timed out during banner exchange`.
- `nc -vz 47.79.99.190 22`
  - Result: TCP port 22 succeeded.
- `dig +short pre-studio.miemie.co A`
  - Result: `198.18.2.63`.
- `route -n get 47.79.99.190`
  - Result: route uses gateway `198.18.0.1` and interface `utun1024`.
- `curl -k -sS ... https://pre-studio.miemie.co/api/health`
  - Result: timed out after 20 seconds with no bytes received.

Interpretation: TCP can reach port 22, but SSH stalls during banner exchange, while the local DNS/route path still goes through fake-IP/TUN. No server command, container restart, or database business switch was executed.

## New Runner

Added `scripts/postgres_staging_video_task_sequence.sh`.

Default behavior is dry-run only:

```bash
scripts/postgres_staging_video_task_sequence.sh
```

To execute on the staging server after SSH is stable:

```bash
CONFIRM_STAGING_SEQUENCE=run scripts/postgres_staging_video_task_sequence.sh
```

Default sequence:

```text
01 audit
02 roll-runtime
03 dual-write-canary
04 read-switch-canary
05 rollback-read-switch
06 primary-write-canary
07 rollback-primary-write
```

The runner creates one artifact subdirectory per stage and stops immediately when a stage exits non-zero. Exit code `2` is recorded as blocked; any other non-zero code is failed.

## Verification

- `bash -n scripts/postgres_staging_video_task_sequence.sh`: passed.
- `python3 scripts/verify_postgres_staging_canary_sequence.py`: passed.
- `python3 scripts/verify_postgres_staging_canary_script.py`: passed.
- Local dry-run wrote the expected sequence and did not execute any canary stage.

## Current Server State

R51 did not execute server commands, restart containers, enable dual-write/read-switch/primary-write, or call a real provider. Server-side staging canary execution remains pending a stable non-TUN SSH command path.
