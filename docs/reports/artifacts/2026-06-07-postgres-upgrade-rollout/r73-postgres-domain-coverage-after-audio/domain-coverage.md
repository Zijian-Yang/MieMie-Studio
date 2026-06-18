# PostgreSQL Domain Coverage Audit

Run ID: `r73-postgres-domain-coverage-after-audio-20260618`
Updated At: `2026-06-18T02:38:34Z`
State: `ready_for_staging_live_data_canary`

## Migrated Domains

| Domain | Status | Present Files | Missing Files |
| --- | --- | --- | --- |
| `video_studio_tasks` | covered | 7 | - |
| `studio_tasks` | covered | 7 | - |
| `projects` | covered | 7 | - |
| `media_metadata` | covered | 7 | - |
| `project_entities` | covered | 7 | - |
| `benchmark_records` | covered | 7 | - |
| `user_config` | covered | 7 | - |
| `sessions` | covered | 7 | - |
| `audio_studio` | covered | 7 | - |

## Pending Domains

| Domain | Status | JSON surfaces | Missing PostgreSQL files |
| --- | --- | --- | --- |

## Covered Embedded Surfaces

| Surface | Covered By | Status |
| --- | --- | --- |
| `scripts/shots` | `projects.raw_project_snapshot` | covered |

## Next Recommended Domain

`staging_live_data_canary` is the next step: all tracked core business-state domains now have local schema/repository/backfill/reconcile/runtime gates, so the remaining risk is server live-data and app-level canary execution.

Recommended rollout:

- Re-run the server `live-data-gate` so Alembic, all-domain backfill/reconcile, backup, and restore rehearsal include the latest sessions and audio studio migrations.
- Continue staging app-level canaries: dual-write, read-switch, rollback-read-switch, primary-write, and rollback-primary-write.
- Keep application runtime file-only until those server gates and rollback checks pass.

## Notes

- `projects.raw_project_snapshot` currently covers project scripts and shots for database migration purposes.
- Binary/generated media objects remain file or OSS assets; this audit tracks business state domains only.
