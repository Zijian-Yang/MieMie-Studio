# R120 PostgreSQL Database Snapshot Dry Run

- Scope: add a read-only PostgreSQL database operational snapshot gate.
- Local dry run: `state=dry_run`, `stage=planned`.
- The gate collects database size, expected table presence, table estimates, relation sizes, index usage, connection counts, long transaction count, and waiting lock count.
- Boundary: dry-run does not execute Docker or psql; no PostgreSQL dumps, row-level user data, credentials, or webhook URLs are stored.
