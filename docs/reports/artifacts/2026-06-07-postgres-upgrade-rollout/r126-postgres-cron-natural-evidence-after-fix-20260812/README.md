# R126 PostgreSQL natural cron evidence after log-directory fix

## Result

- State: `passed`
- Required evidence source: `trigger=cron`
- Strict lower bound: `2026-08-11T16:55:00Z`
- Operational readiness: `passed`
- Backup retention: `passed`; one expired backup was pruned
- Database snapshot: `passed`

## Root cause and fix

The cron daemon was active and did invoke the scheduled commands, but shell
redirection to `logs/*.log` failed before the scripts started because the
repository did not contain a runtime `logs/` directory. The generated cron
commands now create `logs/` and `validation-artifacts/` after entering the
install root and before any redirection or task execution.

The formal cron file was refreshed at `/etc/cron.d/miemie-postgres-ops`. A
short-lived proof cron file triggered all three tasks through the real cron
daemon and was then removed from `/etc/cron.d`; a recoverable copy remains in
`/tmp` on the staging server. No database dump, credential, token, or webhook
URL is included in this artifact.

## Evidence

- `status.json` is the strict evidence gate result.
- `cron-evidence-summary.tsv` names the three cron-produced status files.
- `miemie-postgres-ops.cron` is the installed formal schedule snapshot.
- `cron-service-status.txt` records the scheduler service state.
