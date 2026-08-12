# R128 PostgreSQL session expiry deployment

## Scope

Deploy and verify the PostgreSQL session expiry fix, then ensure tests executed
inside a PostgreSQL-only production container cannot access the live database by
inheriting runtime environment variables.

## Local verification

- Backend full suite: `471 passed`.
- Session repository/read-switch tests under production-style database
  environment variables: `10 passed`.
- Related database mode tests: `25 passed`.
- Frontend typecheck, lint, build, chunk guard, policy tests and Playwright E2E
  were already green for the release candidate and were unaffected by the
  test-only isolation follow-up.

## Server verification

Pending final release synchronization and post-deployment checks. The runtime
canary performed before this follow-up confirmed that a synthetic PostgreSQL
session is readable before expiry, hidden after its expiry timestamp is moved
into the past, and removed in a `finally` cleanup block.
