# Final PostgreSQL JSON Exit Audit

Run ID: `r80-final-json-exit-audit`
Updated At: `2026-06-18T06:08:45Z`
State: `needs_server_sequence_evidence`
Next Recommended Step: `run_server_final_cutover_sequence`

## Expected Domains

`video_studio_tasks`, `studio_tasks`, `projects`, `media_metadata`, `project_entities`, `benchmark_records`, `user_config`, `sessions`, `audio_studio`

## Checks

| Check | State |
| --- | --- |
| `cutover_readiness_contract` | `passed` |
| `server_sequence_evidence` | `needs_work` |
| `final_runtime_policy` | `needs_work` |

## Final Runtime Policy

| Variable | Required Value | Assignment |
| --- | --- | --- |
| `MIEMIE_DATABASE_ENABLED` | `true` | `MIEMIE_DATABASE_ENABLED=true` |
| `MIEMIE_DATABASE_WRITE_MODE` | `postgres` | `MIEMIE_DATABASE_WRITE_MODE=postgres` |
| `MIEMIE_DATABASE_READ_MODE` | `postgres` | `MIEMIE_DATABASE_READ_MODE=postgres` |
| `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS` | `` | `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=` |
| `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS` | `` | `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=` |
| `MIEMIE_DATABASE_READ_DOMAINS` | `` | `MIEMIE_DATABASE_READ_DOMAINS=` |
| `MIEMIE_DATABASE_JSON_FALLBACK_READ` | `false` | `MIEMIE_DATABASE_JSON_FALLBACK_READ=false` |
| `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES` | `false` | `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false` |
| `MIEMIE_DATABASE_RECONCILE_STRICT` | `true` | `MIEMIE_DATABASE_RECONCILE_STRICT=true` |

## Notes

- This audit is read-only and does not mutate compose.env, containers, PostgreSQL, or JSON data.
- ready_for_post_json_exit_validation is not the final done state; it means the post-exit health, reconcile, and load gates can run.
- Final JSON exit requires server sequence evidence, PostgreSQL read/write primary policy, JSON fallback disabled, and JSON archive writes disabled.
