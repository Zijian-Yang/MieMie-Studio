# R120 PostgreSQL Database Snapshot Server Run

- Run ID: `r120-postgres-database-snapshot-server-20260620`
- Scope: collect read-only PostgreSQL operational metadata on `miemie-pre`.
- Result: `state=passed`.
- Key metrics: database size `10607639` bytes, connections `3/50`, long transactions `0`, waiting locks `0`, missing expected tables `0`, warnings `0`.
- Boundary: artifact files are system statistics and table/index metadata only; no PostgreSQL dumps, row-level business data, credentials, webhook URLs, or private user payloads are stored.
