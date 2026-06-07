# R34 Benchmark Records PostgreSQL Primary Write

## Summary

R34 adds feature-flagged PostgreSQL primary-write support for image/video benchmark datasets, suites, and runs.

Default runtime behavior remains JSON/file-only. Benchmark record writes use PostgreSQL as primary only when database support and the `benchmark_records` primary-write domain are explicitly enabled. Optional JSON archive mirror writes can be kept during the cutover window.

## Runtime Flags

- `MIEMIE_DATABASE_ENABLED=true`
- `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=benchmark_records` or `MIEMIE_DATABASE_WRITE_MODE=postgres|postgres_primary|primary`
- `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false` writes/deletes only PostgreSQL in primary mode
- `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` also maintains a temporary JSON archive mirror

## Changed Files

- `backend/app/repositories/benchmark_record_runtime.py`
- `backend/app/services/storage.py`
- `backend/tests/test_benchmark_record_primary_write.py`

## Verification

- RED gate: `backend/.venv/bin/pytest backend/tests/test_benchmark_record_primary_write.py -q`
  - Expected failure before implementation: missing `build_benchmark_record_primary_repository`
- Focused green: `backend/.venv/bin/pytest backend/tests/test_benchmark_record_primary_write.py -q`
  - Result: `4 passed`
- Compile: `backend/.venv/bin/python -m py_compile backend/app/repositories/benchmark_record_runtime.py backend/app/services/storage.py backend/app/repositories/benchmark_records.py`
  - Result: passed
- Target set: `backend/.venv/bin/pytest backend/tests/test_benchmark_record_primary_write.py backend/tests/test_benchmark_record_read_switch.py backend/tests/test_benchmark_record_dual_write.py backend/tests/test_benchmark_record_migration.py backend/tests/test_benchmark_record_repository.py backend/tests/test_benchmark_record_schema.py backend/tests/test_storage_service.py -q`
  - Result: `21 passed`
- Full backend: `backend/.venv/bin/pytest backend/tests -q`
  - Result: `366 passed`

## Notes

- PostgreSQL primary write failures propagate and do not write JSON, avoiding split-brain during cutover.
- No backend API response shape changed.
- No frontend behavior changed.
- No server state changed in this step.
