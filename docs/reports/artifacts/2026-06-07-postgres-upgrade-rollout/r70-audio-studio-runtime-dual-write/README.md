# R70 Audio Studio Runtime Dual-Write

Date: 2026-06-17

## Summary

R70 adds opt-in runtime PostgreSQL shadow writes for the `audio_studio` domain.

- Added runtime feature flag boundary: `backend/app/repositories/audio_studio_runtime.py`.
- Connected `StorageService` audio task save/delete paths to shadow PostgreSQL writes.
- Connected `StorageService` voice profile save/delete paths to shadow PostgreSQL writes.
- Default runtime remains JSON/file-only.
- Shadow writes only run when database is enabled and `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=audio_studio` or global dual-write mode is explicitly configured.
- Shadow failures are warning-only by default and propagate only when `MIEMIE_DATABASE_RECONCILE_STRICT=true`.

This step does not add PostgreSQL reads or primary writes. R71/R72 remain separate gates.

## Verification

- RED: `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_dual_write.py -q` failed before implementation because `app.repositories.audio_studio_runtime` did not exist.
- GREEN: `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_dual_write.py -q` -> `4 passed`.
- `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_dual_write.py backend/tests/test_audio_studio_migration.py backend/tests/test_audio_studio_repository.py backend/tests/test_audio_studio_schema.py -q` -> `15 passed`.
- `python3 scripts/verify_postgres_domain_coverage.py` -> passed after the coverage contract moved `audio_studio` to covered local migration foundation.

## Server State

No server command was executed in R70 and no business database flag was enabled on staging.

Remaining `audio_studio` steps:

- R71 read-switch canary with JSON fallback.
- R72 primary-write canary plus JSON archive mirror.
