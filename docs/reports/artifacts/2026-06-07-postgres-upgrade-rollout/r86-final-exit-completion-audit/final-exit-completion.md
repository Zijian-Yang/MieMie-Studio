# PostgreSQL Final Exit Completion Audit

- Run ID: `r86-final-exit-completion-audit`
- State: `needs_final_exit_evidence`
- Next recommended step: `run_server_final_exit_sequence`
- Final exit artifact dir: `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r84-server-final-exit-sequence`

## Checks

| Check | State | Observed | Reason |
| --- | --- | --- | --- |
| `server_final_exit_status` | `needs_work` | `dry_run` | set CONFIRM_SERVER_FINAL_EXIT_SEQUENCE=run to execute on the server |
| `server_sequence_wrapper` | `needs_work` | `` | missing status file |
| `server_sequence_inner` | `needs_work` | `` | missing status file |
| `apply_final_policy` | `needs_work` | `` | missing status file |
| `apply_final_policy_audit` | `needs_work` | `` | missing status file |
| `post_json_exit_validation` | `needs_work` | `` | missing status file |
| `post_validation_audit` | `needs_work` | `` | missing status file |
| `rollback_not_triggered` | `passed` | `` | no rollback status artifact found |

## Completion Requirements

- server final exit sequence status is passed
- server staging sequence wrapper and inner sequence are passed
- final PostgreSQL-only policy application is passed
- final JSON exit audit is ready_for_post_json_exit_validation before and during post validation
- post JSON exit validation is passed
- rollback did not pass after the final exit attempt

## Notes

- This audit is read-only and never mutates compose.env, PostgreSQL, JSON files, or containers.
- postgres_only_complete means runtime evidence says JSON is no longer primary or fallback business-state storage.
- It does not delete historical JSON files; archival/deletion is a separate operator action after monitoring.
