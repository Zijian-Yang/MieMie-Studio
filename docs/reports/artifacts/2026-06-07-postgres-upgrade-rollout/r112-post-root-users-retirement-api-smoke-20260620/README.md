# R112 Post-Root-Users Retirement API Smoke

## Summary

- Run ID: `r112-post-root-users-retirement-api-smoke-20260620`
- Result: `ok=true`
- Purpose: provider-free API smoke after retiring root `users.json`

## Covered Path

The smoke registered a one-time user, created a project, confirmed listing visibility, deleted it, confirmed removal, and logged out while the runtime was PostgreSQL-only.

The artifact records only IDs and booleans. It does not store the auth token or password.
