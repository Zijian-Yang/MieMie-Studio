# R50 Staging Primary Write Rollback Automation

2026-06-17 extended the staging PostgreSQL canary script from read-switch gates into primary-write and primary-write rollback gates.

## Scope

- Extend `scripts/postgres_staging_video_task_canary.sh`.
- Add explicit `MODE=primary-write-canary`.
- Add explicit `MODE=rollback-primary-write`.
- Keep `MODE=audit` as the default.
- Keep provider pressure out of the gate: API smoke still uses `/api/video-studio/preview-payload`.

## New Sequence

After SSH command execution is stable and earlier modes pass, the extended server sequence is:

```bash
MODE=audit scripts/postgres_staging_video_task_canary.sh
MODE=roll-runtime scripts/postgres_staging_video_task_canary.sh
MODE=dual-write-canary scripts/postgres_staging_video_task_canary.sh
MODE=read-switch-canary scripts/postgres_staging_video_task_canary.sh
MODE=rollback-read-switch scripts/postgres_staging_video_task_canary.sh
MODE=primary-write-canary scripts/postgres_staging_video_task_canary.sh
MODE=rollback-primary-write scripts/postgres_staging_video_task_canary.sh
```

## Primary Source Proof

`primary-write-canary` enables:

- `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=video_studio_tasks`
- `MIEMIE_DATABASE_READ_DOMAINS=video_studio_tasks`
- `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false`

The maintenance canary then writes through `StorageService.save_video_studio_task()` and verifies:

- PostgreSQL row exists;
- read-after-write returns the PostgreSQL row;
- no JSON archive file was created.

`rollback-primary-write` clears primary-write/read domains and enables JSON primary with PostgreSQL shadow writes. It writes a divergent JSON/PG canary status and verifies:

- JSON file exists after write;
- read-after-write returns the JSON status;
- PostgreSQL shadow row exists;
- delete removes JSON and marks the PostgreSQL shadow row deleted.

## Verification

- `bash -n scripts/postgres_staging_video_task_canary.sh`: passed.
- `python3 scripts/verify_postgres_staging_canary_script.py`: passed.
- `python3 -m py_compile scripts/verify_postgres_staging_canary_script.py`: passed.
- `backend/.venv/bin/pytest backend/tests/test_video_studio_task_primary_write.py backend/tests/test_video_studio_task_read_switch.py backend/tests/test_video_studio_task_dual_write.py -q`: 11 passed.

The verifier compiles every embedded `<<'PY'` heredoc block and checks that primary-write and rollback-primary modes remain present in the script safety contract.

Note: the same targeted pytest command failed under the older root `venv` because that environment did not have `sqlalchemy` installed. The project-declared backend environment `backend/.venv` contains SQLAlchemy and was used for the passing run.

## Current Server State

R50 did not execute server commands, restart containers, enable primary-write, or enable any database business switch. Server execution remains pending a stable SSH command path.
