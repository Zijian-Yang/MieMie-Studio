# R71 audio_studio read-switch

## Summary

R71 adds an opt-in PostgreSQL read switch for `audio_studio` while keeping the default runtime file-only. The switch covers audio task reads, audio task project lists, voice profile reads, voice profile project lists, and voice profile lookup by DashScope `voice_id`.

## Runtime Boundary

- Default runtime remains JSON/file-only.
- PostgreSQL reads are enabled only when `MIEMIE_DATABASE_ENABLED=true` and either `MIEMIE_DATABASE_READ_DOMAINS=audio_studio` or `MIEMIE_DATABASE_READ_MODE=postgres`.
- `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` falls back to JSON on PostgreSQL miss, empty project list, or read error.
- This step does not add primary-write behavior, does not change public API shapes, and does not execute server commands.

## Changed Code

- `backend/app/repositories/audio_studio_runtime.py`
  - Added read flags, read repository builder, and JSON fallback helpers.
- `backend/app/services/storage.py`
  - Routed audio task and voice profile read methods through the runtime read helpers.
- `backend/tests/test_audio_studio_read_switch.py`
  - Added TDD coverage for default file-only behavior, PostgreSQL read preference, JSON fallback, and fallback-disabled error propagation.

## Verification

- RED: `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_read_switch.py -q` failed before implementation because `build_audio_studio_read_repository` was missing.
- GREEN: `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_read_switch.py -q` passed (`4 passed`).
- Domain coverage report generated in this artifact directory.
- `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_read_switch.py backend/tests/test_audio_studio_dual_write.py backend/tests/test_audio_studio_migration.py backend/tests/test_audio_studio_repository.py backend/tests/test_audio_studio_schema.py -q` passed (`19 passed`).
- `backend/.venv/bin/python -m pytest backend/tests/ -q` passed (`443 passed`).

## Next Step

R72 should add `audio_studio` PostgreSQL primary-write with optional JSON archive mirror. Keep the default runtime file-only until staging live-data and canary gates pass.
