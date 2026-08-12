# Phase 7B Platform Operations Evidence

This directory stores sanitized evidence for administrator-configured PostgreSQL backups, Aliyun OSS off-site copies, generic Webhook delivery, the dedicated `ops` worker, and the daily scheduler.

## Evidence Rules

- Never store administrator/member tokens, passwords, the platform encryption key, OSS credentials, raw Webhook URLs, database URLs, request bodies, or provider payloads.
- Store only stable status categories, masked configuration flags, checksums, sizes, relative artifact paths, container health, migration head, and provider-call count.
- Real restore evidence must target an isolated temporary database and must not overwrite the production database.
- `pg_dump`, `pg_restore`, and the PostgreSQL server must use the same major version; a version mismatch blocks backup publication.
- Real OSS test objects are deleted; one validated backup object may remain as the off-site recovery artifact when documented by object key only.

## Expected Server Evidence

- pre-upgrade database dump and checksum
- Alembic head `20260812_0011`
- API, PostgreSQL, Redis, `worker`, `worker-video`, `worker-ops`, and scheduler health
- provider-free platform operations smoke
- real Webhook receipt with fixed event schema
- real Aliyun OSS upload, checksum, and isolated restore rehearsal
- two idempotent scheduler date runs before legacy cron removal
- post-deployment S1 and secret scan
