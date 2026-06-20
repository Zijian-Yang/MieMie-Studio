# R111 Root Users JSON Retirement

## Summary

- Run ID: `r111-root-users-json-retirement-20260620`
- Result: `passed`
- JSON user count: `51`
- PostgreSQL active user count: `53`
- Missing JSON users in PostgreSQL: `0`

## Action

After confirming every user ID in root `backend/data/users.json` existed in PostgreSQL, the server created `validation-artifacts/r111-root-users-json-retirement-20260620/users-json-before-retirement.r111-root-users-json-retirement-20260620.tar.gz` and moved the root file to `backend/data/_postgres_final_json_archive/r111-root-users-json-retirement-20260620/users.json`.

## Repository Safety

The tarball and quarantined `users.json` contain user records and intentionally remain on the server. The repository stores only counts, status, and remaining JSON summary.
