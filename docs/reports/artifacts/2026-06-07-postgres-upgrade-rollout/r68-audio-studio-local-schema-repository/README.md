# R68 Audio Studio Local Schema/Repository

Date: 2026-06-17

## Summary

R68 starts the `audio_studio` PostgreSQL migration domain identified by the R67 coverage audit.

- Added schema file: `backend/app/db/schema/audio_studio.py`.
- Added Alembic migration: `backend/app/db/migrations/versions/20260617_0009_audio_studio.py`.
- Added repository boundary: `backend/app/repositories/audio_studio.py`.
- Added repository protocol entries for audio studio tasks and voice profiles.
- Added tests for schema DDL/indexes, file repository behavior, row mapping, and dual-write wrapper behavior.

The new schema contains two tables:

- `audio_studio_tasks`: audio generation, TTS, voice clone, and voice design task state.
- `voice_profiles`: cloned/designed voice profile metadata and lookup state.

Both tables keep the full Pydantic model in JSONB snapshots while exposing conservative index columns for project lists, status scans, and voice-id lookup.

## Verification

- RED: `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_schema.py backend/tests/test_audio_studio_repository.py -q` failed before implementation because `app.db.schema.audio_studio` and `app.repositories.audio_studio` did not exist.
- GREEN: `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_schema.py backend/tests/test_audio_studio_repository.py -q` -> `9 passed`.
- `python3 scripts/verify_postgres_domain_coverage.py` -> passed after updating the coverage contract to report `audio_studio` as `in_progress`.
- `python3 -m py_compile scripts/postgres_domain_coverage.py scripts/verify_postgres_domain_coverage.py backend/app/repositories/audio_studio.py backend/app/db/schema/audio_studio.py backend/app/db/migrations/versions/20260617_0009_audio_studio.py` -> passed.
- `MIEMIE_DATABASE_URL=postgresql+psycopg://miemie:local@postgres:5432/miemie backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head --sql` -> passed and rendered `20260617_0009`.
- `backend/.venv/bin/python -m pytest backend/tests/ -q` -> `433 passed`.

## Server State

No runtime path was switched and no server command was executed in R68.

Remaining `audio_studio` steps:

- R69 backfill/reconcile with redacted voice metadata.
- R70 runtime dual-write.
- R71 read-switch canary with JSON fallback.
- R72 primary-write canary plus JSON archive mirror.
