# R69 Audio Studio Backfill/Reconcile

Date: 2026-06-17

## Summary

R69 adds local migration tooling for the `audio_studio` PostgreSQL domain started in R68.

- Added backfill service: `backend/app/services/migration/backfill_audio_studio.py`.
- Added reconcile service: `backend/app/services/migration/reconcile_audio_studio.py`.
- Added CLI wrappers:
  - `scripts/postgres_backfill_audio_studio.py`
  - `scripts/postgres_reconcile_audio_studio.py`
- Extended local/live PostgreSQL rehearsal domain lists so `audio_studio` participates in future full-domain gates.

The backfill scans both per-user JSON surfaces:

- `users/<user_id>/audio_studio/*.json` for audio studio tasks.
- `users/<user_id>/voices/*.json` for cloned/designed voice profiles.

Reconcile output compares only conservative fields such as ids, project ids, statuses, task type, result voice id, source, target model, and timestamps. It intentionally does not emit task text, prompts, audio URLs, names, provider payloads, tokens, keys, or passwords.

## Verification

- RED: `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_migration.py -q` failed before implementation because `app.services.migration.backfill_audio_studio` did not exist.
- GREEN: `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_migration.py -q` -> `2 passed`.
- `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_migration.py backend/tests/test_audio_studio_repository.py backend/tests/test_audio_studio_schema.py -q` -> `11 passed`.
- `python3 scripts/verify_postgres_domain_coverage.py` -> passed.
- `backend/.venv/bin/python -m py_compile backend/app/services/migration/backfill_audio_studio.py backend/app/services/migration/reconcile_audio_studio.py scripts/postgres_backfill_audio_studio.py scripts/postgres_reconcile_audio_studio.py scripts/postgres_domain_coverage.py scripts/verify_postgres_domain_coverage.py` -> passed.

## Server State

No runtime path was switched and no server command was executed in R69.

Remaining `audio_studio` steps:

- R70 runtime dual-write.
- R71 read-switch canary with JSON fallback.
- R72 primary-write canary plus JSON archive mirror.
