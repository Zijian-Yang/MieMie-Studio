# Final PostgreSQL Cutover Readiness Audit

Run ID: `r75-final-cutover-readiness`
Updated At: `2026-06-18T03:32:00Z`
State: `needs_all_domain_app_canary`
Next Recommended Step: `add_all_domain_app_canary`

## Expected Domains

`video_studio_tasks`, `studio_tasks`, `projects`, `media_metadata`, `project_entities`, `benchmark_records`, `user_config`, `sessions`, `audio_studio`

## Checks

| Check | State | Source |
| --- | --- | --- |
| `domain_coverage` | `passed` | `scripts/postgres_domain_coverage.py` |
| `live_data_gate_domains` | `passed` | `scripts/postgres_staging_live_data_gate.sh` |
| `staging_sequence_order` | `passed` | `scripts/postgres_staging_video_task_sequence.sh` |
| `server_fallback_contract` | `passed` | `scripts/pre_studio_server_postgres_sequence.sh` |
| `app_canary_domain_coverage` | `needs_work` | `scripts/postgres_staging_video_task_canary.sh` |

## App Canary Coverage Gap

Covered domains: `video_studio_tasks`

Missing domains: `audio_studio`, `benchmark_records`, `media_metadata`, `project_entities`, `projects`, `sessions`, `studio_tasks`, `user_config`

The current staging app-level canary is intentionally provider-free but only proves `video_studio_tasks`. Before final database-primary cutover, add an all-domain provider-free canary or smoke gate that exercises write/read/delete semantics for every migrated domain.

## Notes

- This audit is read-only and does not touch server containers or business data.
- A passed domain coverage audit is necessary but not sufficient for final JSON exit.
- Final cutover still requires live server execution evidence for live-data, app canaries, rollback, and post-cutover health/load gates.
