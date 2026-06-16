# R45 Staging Canary Automation Script

2026-06-17 added a repeatable server-side gate script for resuming the interrupted R44 staging canary.

## Scope

- Add `scripts/postgres_staging_video_task_canary.sh`.
- Keep the script safe by default: `MODE=audit` performs read-only checks.
- Require explicit `MODE=roll-runtime` before rebuilding/restarting API and workers.
- Require explicit `MODE=dual-write-canary` before enabling `video_studio_tasks` dual-write.
- Avoid real provider calls during canary validation.

## Script Modes

```bash
MODE=audit scripts/postgres_staging_video_task_canary.sh
MODE=roll-runtime scripts/postgres_staging_video_task_canary.sh
MODE=dual-write-canary scripts/postgres_staging_video_task_canary.sh
```

The intended server sequence is:

1. `MODE=audit` after SSH recovers, to inspect the interrupted R44 build state.
2. `MODE=roll-runtime`, keeping `MIEMIE_DATABASE_ENABLED=false`, until `/api/health` reports the current repo commit.
3. `MODE=dual-write-canary`, enabling only `video_studio_tasks` shadow writes.

## Safety

- The script redacts PostgreSQL password and database URL in committed artifacts.
- API smoke stores token/password only under the script tmp dir, not in the artifact dir.
- The video task write smoke uses an in-container maintenance write through `StorageService.save_video_studio_task()` and checks PostgreSQL shadow state directly; it does not submit a real provider task.
- `POST /api/video-studio/preview-payload` is used only as a no-provider API smoke.

## Local Verification

- `bash -n scripts/postgres_staging_video_task_canary.sh`: passed.
- Local dry precheck with no server `compose.env`: exited `2` and wrote a blocked status instead of trying Docker/Compose actions.

## Current Blocker

Server execution is still waiting on a clean direct SSH path. At the time of this artifact, local DNS/route still showed the fake-IP/TUN pattern:

- `pre-studio.miemie.co` resolved to `198.18.2.63`.
- route to `47.79.99.190` used `utun1024` via `198.18.0.1`.
- TCP 22 connected, but SSH timed out during banner exchange.
