# R119 PostgreSQL Operational Cron Evidence Gate

- Scope: add a reusable gate for scheduled PostgreSQL cron evidence.
- Local dry run: `state=dry_run`, `stage=planned`.
- Purpose: distinguish the normal pre-first-run `waiting` state from a failed operational readiness or backup retention cron run.
- Boundary: this artifact contains only the generated plan and status; it does not include cron logs, webhook URLs, PostgreSQL dumps, or private user data.
