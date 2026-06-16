# R43 Staging Live Migration Backfill Reconcile

2026-06-16 completed the first server-side PostgreSQL live data gates for `miemie-pre`.

## Scope

- Recover SSH after R42.
- Confirm existing API runtime health remained `200`.
- Use a temporary server-side maintenance venv under `/tmp`.
- Run Alembic against the staging PostgreSQL container.
- Run all domain backfill and reconcile scripts.
- Run PostgreSQL backup and restore rehearsal.
- Keep all application database read/write switches disabled.

## Result

- `alembic upgrade head`: passed.
- Alembic head: `20260607_0007`.
- Backfill: passed for all domains.
- Reconcile: passed for all domains.
- Backup: produced a server-side SQL backup.
- Restore rehearsal: passed with `miemie_restore_check`.
- Server-local health after gates: `HTTP 200`.
- Server-side public Cloudflare health after gates: `HTTP 200`.
- `MIEMIE_DATABASE_ENABLED` for application runtime remains disabled; no app traffic was switched to PostgreSQL.
- Closeout read-only check at `2026-06-16 23:27 CST`: `api`, `postgres`, `redis`, `worker`, and `worker-video` were still up; server-local and Cloudflare `/api/health` both returned `200`.

## Sanitized Counts

See `sanitized-summary.json`.

```json
{
  "video_studio_tasks": 6,
  "studio_tasks": 12,
  "projects": 9,
  "media_assets": 0,
  "text_items": 0,
  "project_entities": 0,
  "benchmark_records": 0,
  "users": 46,
  "user_configs": 40
}
```

## Evidence

- `sanitized-summary.json`
- `health-after-db-gates.headers`
- `health-after-db-gates.json`
- `public-health-after-db-gates.headers`
- `public-health-after-db-gates.json`
- `compose-ps-after-db-gates.txt`
- `backup.stdout.txt`
- `restore.stdout.txt`

Raw backfill/reconcile stdout stayed on the server because it includes live user UUIDs. The committed artifact only contains sanitized counts and non-secret health/restore evidence.

## Next

Run the first staging application-level database gate with conservative flags:

1. Enable database support for runtime while keeping writes file-primary.
2. Enable one low-risk dual-write domain first, preferably `video_studio_tasks`.
3. Run health, smoke, and reconcile.
4. Only then progress to read-switch and PostgreSQL-primary gates.
