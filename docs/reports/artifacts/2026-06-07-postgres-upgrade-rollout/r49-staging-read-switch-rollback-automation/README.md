# R49 Staging Read Switch Rollback Automation

2026-06-17 extended the staging PostgreSQL canary script beyond dual-write into read-switch and read rollback gates.

## Scope

- Extend `scripts/postgres_staging_video_task_canary.sh`.
- Add explicit `MODE=read-switch-canary`.
- Add explicit `MODE=rollback-read-switch`.
- Keep the script safe by default: `MODE=audit` remains the default and no server action runs without an explicit mode.
- Keep provider pressure out of this gate: API smoke still uses `/api/video-studio/preview-payload`.

## New Sequence

After SSH command execution is stable, the intended server sequence is:

```bash
MODE=audit scripts/postgres_staging_video_task_canary.sh
MODE=roll-runtime scripts/postgres_staging_video_task_canary.sh
MODE=dual-write-canary scripts/postgres_staging_video_task_canary.sh
MODE=read-switch-canary scripts/postgres_staging_video_task_canary.sh
MODE=rollback-read-switch scripts/postgres_staging_video_task_canary.sh
```

## Read Source Proof

The new canaries create a temporary divergent task:

- JSON copy has status `json_read_canary`.
- PostgreSQL copy has status `postgres_read_canary`.

`read-switch-canary` expects `StorageService.get_video_studio_task()` and project list reads to return the PostgreSQL status. `rollback-read-switch` expects the same read paths to return the JSON status after `MIEMIE_DATABASE_READ_DOMAINS` is cleared. Both canaries clean up their JSON file and PostgreSQL row in a `finally` block.

## Verification

- `bash -n scripts/postgres_staging_video_task_canary.sh`: passed.
- `python3 scripts/verify_postgres_staging_canary_script.py`: passed.
- `python3 -m py_compile scripts/verify_postgres_staging_canary_script.py`: passed.

The verifier now also compiles every embedded `<<'PY'` heredoc block, so shell and maintenance Python syntax are both covered locally.

## Current Server State

R49 did not execute server commands, restart containers, enable read-switch, or enable any database business switch. Server execution remains pending a stable SSH command path.
