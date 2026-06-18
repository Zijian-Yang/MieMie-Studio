# R72 audio_studio primary-write

## Summary

R72 adds opt-in PostgreSQL primary-write for `audio_studio`, completing the local migration gate for audio tasks and voice profiles. The default runtime remains JSON/file-only.

## Runtime Boundary

- Primary writes are enabled only when `MIEMIE_DATABASE_ENABLED=true` and either `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=audio_studio` or `MIEMIE_DATABASE_WRITE_MODE=postgres|postgres_primary|primary`.
- When primary-write is enabled, audio task and voice profile saves/deletes write PostgreSQL first.
- JSON archive mirrors are written only when `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true`.
- PostgreSQL primary failures propagate and do not write JSON, avoiding split-brain during cutover.
- This step does not execute server commands and does not enable production/staging business database flags.

## Changed Code

- `backend/app/repositories/audio_studio_runtime.py`
  - Added primary-write flag, primary repository builder, save/delete helpers, and JSON archive flag.
- `backend/app/services/storage.py`
  - Routed audio task and voice profile save/delete through PostgreSQL primary-write helpers when explicitly enabled.
- `backend/tests/test_audio_studio_primary_write.py`
  - Added TDD coverage for default disabled behavior, PostgreSQL primary save/delete, optional JSON archive mirror, and failure-no-JSON behavior.

## Verification

- RED: `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_primary_write.py -q` failed before implementation because `build_audio_studio_primary_repository` was missing.
- GREEN: `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_primary_write.py -q` passed (`4 passed`).
- Domain coverage report generated in this artifact directory.
- `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_primary_write.py backend/tests/test_audio_studio_read_switch.py backend/tests/test_audio_studio_dual_write.py backend/tests/test_audio_studio_migration.py backend/tests/test_audio_studio_repository.py backend/tests/test_audio_studio_schema.py -q` passed (`23 passed`).
- `backend/.venv/bin/python -m pytest backend/tests/ -q` passed (`447 passed`).

## Next Step

The `audio_studio` local domain now has schema/repository, backfill/reconcile, runtime dual-write, read-switch, and primary-write gates. Next work should return to staging live-data/canary gates or run a fresh coverage audit to decide whether any non-core JSON-only state remains.
