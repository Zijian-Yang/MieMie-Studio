# R128 PostgreSQL session expiry deployment

## Scope

Deploy and verify the PostgreSQL session expiry fix, then ensure tests executed
inside a PostgreSQL-only production container cannot access the live database by
inheriting runtime environment variables.

## Local verification

- Backend full suite before server-side test discovery: `471 passed`.
- Session repository/read-switch tests under production-style database
  environment variables: `10 passed`.
- Related database mode tests: `25 passed`.
- Frontend typecheck, lint, build, chunk guard, policy tests and Playwright E2E
  were already green for the release candidate and were unaffected by the
  test-only isolation follow-up.

## Server verification

Release `8af54559b57a43fee7b54ba5c3428fb13470a388` reached the server and local and
public health both reported Redis/PostgreSQL healthy with the matching runtime
version. Direct origin HTTP and HTTPS remained denied with `403`.

The production-container session tests passed `10` tests, but revealed a test
helper side effect: helpers constructed the default `UserService` before
changing its data directory, which created an empty `backend/data/users.json`
in the live bind mount. Runtime policy and API health remained PostgreSQL-only;
the empty file was detected by the R129 remaining-JSON gate. The follow-up adds
an initialization-time `data_dir` parameter, migrates all affected helpers, and
passes the expanded backend suite with `472` tests before final redeployment.

The runtime canary confirmed that a synthetic PostgreSQL session is readable
before expiry, hidden after its expiry timestamp is moved into the past, and
removed in a `finally` cleanup block.
