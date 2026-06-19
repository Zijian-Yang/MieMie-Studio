# Final PostgreSQL Cutover Readiness Audit

Run ID: `r102-server-final-exit-sequence-health-engine-cache-20260619-server-sequence-readiness-precheck`
Updated At: `2026-06-19T10:18:14Z`
State: `ready_for_final_cutover_sequence`
Next Recommended Step: `run_server_final_cutover_sequence`

## Expected Domains

`video_studio_tasks`, `studio_tasks`, `projects`, `media_metadata`, `project_entities`, `benchmark_records`, `user_config`, `sessions`, `audio_studio`

## Checks

| Check | State | Source |
| --- | --- | --- |
| `domain_coverage` | `passed` | `scripts/postgres_domain_coverage.py` |
| `live_data_gate_domains` | `passed` | `scripts/postgres_staging_live_data_gate.sh` |
| `staging_sequence_order` | `passed` | `scripts/postgres_staging_video_task_sequence.sh` |
| `server_fallback_contract` | `passed` | `scripts/pre_studio_server_postgres_sequence.sh` |
| `app_canary_domain_coverage` | `passed` | `scripts/postgres_staging_all_domain_canary.sh` |

## App Canary Coverage Gap

Covered domains: `video_studio_tasks`, `studio_tasks`, `projects`, `media_metadata`, `project_entities`, `benchmark_records`, `user_config`, `sessions`, `audio_studio`

Missing domains: -

The all-domain provider-free canary contract is present and covers every tracked migrated domain. Final cutover still requires server execution evidence for the live-data gate, all-domain canaries, rollback checks, and post-cutover health/load gates.

## Notes

- This audit is read-only and does not touch server containers or business data.
- A passed domain coverage audit is necessary but not sufficient for final JSON exit.
- Final cutover still requires live server execution evidence for live-data, app canaries, rollback, and post-cutover health/load gates.
