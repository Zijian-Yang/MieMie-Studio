# R129 current-release PostgreSQL operational readiness

## Result

Release `44754d9fd7cc728a01286318381205ad309feda4` passed the current-release
PostgreSQL-only operational gate after the production-container test data-dir
side effect was fixed and the empty test-created `users.json` was moved to a
recoverable server-local quarantine path.

- Gate: `24 passed / 0 warn / 0 blocked / 0 failed`.
- Final runtime policy: PostgreSQL global read/write, JSON fallback and archive
  writes disabled, strict reconcile enabled, domain allowlists empty.
- Local and public health: passed with Redis and PostgreSQL healthy.
- Remaining runtime JSON: only `backend/data/config.example.json`.
- Fresh PostgreSQL backup: passed; SQL dump remains server-local.
- Isolated restore rehearsal: passed.
- Production-container session tests: `10 passed`; `users.json` was absent both
  before and after the run.

The first R129 attempt correctly blocked because those tests had generated an
empty `{}` users file in the live bind mount. File timestamps, contents and the
helper call path identified the cause; no business record was stored in that
file and the API remained PostgreSQL-only.
