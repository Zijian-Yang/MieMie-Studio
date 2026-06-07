# R41 Local Live Database Rehearsal

2026-06-07 added a repeatable local PostgreSQL live rehearsal gate.

## Scope

- Add `scripts/postgres_live_rehearsal.sh`.
- Start a temporary Compose PostgreSQL service with a non-committed password.
- Run `alembic upgrade head`.
- Run all PostgreSQL backfill and reconcile scripts for:
  - `video_studio_tasks`
  - `studio_tasks`
  - `projects`
  - `media_metadata`
  - `project_entities`
  - `benchmark_records`
  - `user_config`
- Run PostgreSQL backup and restore rehearsal.
- Write sanitized artifacts only; raw database passwords are kept under `/tmp` and not committed.

## Current Run

Command:

```bash
RUN_ID=r41-local-live-database-rehearsal-20260607 \
ARTIFACT_DIR=/Users/zane/Project/Miemie-studio-ha-lab/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r41-local-live-database-rehearsal \
TMP_DIR=/tmp/r41-local-live-database-rehearsal-20260607 \
bash scripts/postgres_live_rehearsal.sh
```

Result:

- `state`: `blocked`
- `stage`: `docker-precheck`
- `reason`: `docker daemon unavailable; see docker-info.err`

Evidence:

- `status.json`
- `docker-info.err`
- `commands.log`

## Security

No raw token, provider key, PostgreSQL password, session, or private user data is written to this artifact.

## Next

Start Docker Desktop locally or run the same script from a host with Docker daemon access. After it passes, resume staging rollout with server-side PostgreSQL health, live migration, backfill/reconcile, dual-write, read-switch, and primary-write gates.
