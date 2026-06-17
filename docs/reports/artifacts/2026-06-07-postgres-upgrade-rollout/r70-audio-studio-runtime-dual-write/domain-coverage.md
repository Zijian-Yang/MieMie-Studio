# PostgreSQL Domain Coverage Audit

Run ID: `r70-audio-studio-runtime-dual-write-20260617`
Updated At: `2026-06-17T15:06:24Z`
State: `ready_for_runtime_completion`

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

## Pending Domains

| Domain | Status | JSON surfaces | Missing PostgreSQL files |
| --- | --- | --- | --- |
| `audio_studio` | covered | `audio_studio/*.json`, `voices/*.json` |  |

## Covered Embedded Surfaces

| Surface | Covered By | Status |
| --- | --- | --- |
| `scripts/shots` | `projects.raw_project_snapshot` | covered |

## Next Recommended Domain

`audio_studio` should be the next PostgreSQL migration domain because it is still direct JSON state under `audio_studio/*.json` and `voices/*.json`, is project-scoped, participates in project cleanup, and can follow the same schema/repository/backfill/reconcile/runtime-gate pattern without provider load testing.

Recommended rollout:

- R68 local schema/repository for audio tasks and voice profiles
- R69 backfill/reconcile with redacted voice metadata
- R70 runtime dual-write with JSON primary and PostgreSQL shadow writes
- R71 read-switch canary with JSON fallback
- R72 primary-write canary plus JSON archive mirror

## Notes

- `projects.raw_project_snapshot` currently covers project scripts and shots for database migration purposes.
- Binary/generated media objects remain file or OSS assets; this audit tracks business state domains only.
