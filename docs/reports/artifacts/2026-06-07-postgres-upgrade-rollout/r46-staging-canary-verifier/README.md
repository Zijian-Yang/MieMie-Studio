# R46 Staging Canary Verifier

2026-06-17 added an app-free verifier for the R45 staging canary script.

## Scope

- Add `scripts/verify_postgres_staging_canary_script.py`.
- Keep verification outside `backend/tests/`, because the backend pytest tree loads the full app fixture and local OSS/PyCryptodome native module state.
- Verify the R45 shell script without Docker daemon, server files, app imports, provider keys, or real provider calls.

## Verification

- `python3 scripts/verify_postgres_staging_canary_script.py`: passed.
- `bash -n scripts/postgres_staging_video_task_canary.sh`: passed.

The verifier checks:

- shell syntax;
- missing `compose.env` exits `2` with a blocked precheck artifact;
- missing-env precheck does not touch Docker/Compose;
- the default mode remains `audit`;
- `roll-runtime` keeps database business switches disabled;
- `dual-write-canary` is scoped to `video_studio_tasks`;
- the smoke path uses `StorageService.save_video_studio_task()` and `/api/video-studio/preview-payload`, not a real provider generation endpoint;
- PostgreSQL password and database URL redaction markers remain present.

## Local Pytest Note

An earlier focused attempt to place these checks under `backend/tests/test_run_script.py` hit local environment setup before the test body: `backend/tests/conftest.py` imports `app.main`, which imports the OSS stack, and the local PyCryptodome `_cpuid_c.abi3.so` native module is blocked by macOS system policy. The new verifier avoids that unrelated app import path and is the intended local gate for this shell script.

## Current Blocker

Server execution is still waiting on a clean direct SSH path. The latest local probe showed TCP 22 reachable, but SSH timed out during banner exchange while the route still used the local TUN/fake-IP path. No container restart, no database business switch, and no staging canary traffic occurred in R46.
