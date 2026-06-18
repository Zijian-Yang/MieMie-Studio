# R73 PostgreSQL domain coverage after audio

## Summary

R73 refreshes the PostgreSQL domain coverage audit after completing `audio_studio` R68-R72. The audit now treats `audio_studio` as a migrated local domain instead of a pending domain.

## Result

- Migrated/covered domains: `9`
- Pending tracked core business-state domains: `0`
- Covered embedded surface: `scripts/shots` via `projects.raw_project_snapshot`
- Next recommended step: `staging_live_data_canary`

## Verification

- `python3 scripts/verify_postgres_domain_coverage.py` passed.
- `python3 scripts/postgres_domain_coverage.py --artifact-dir docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r73-postgres-domain-coverage-after-audio --run-id r73-postgres-domain-coverage-after-audio-20260618` generated this artifact.

## Next Step

Return to server gates: run live-data gate so Alembic, all-domain backfill/reconcile, backup, and restore rehearsal include the latest sessions and audio studio migrations; then continue app-level dual-write/read-switch/primary-write canaries and rollback checks.
