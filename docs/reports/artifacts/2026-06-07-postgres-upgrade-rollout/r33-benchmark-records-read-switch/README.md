# R33 Benchmark Records Read Switch

## Summary

R33 adds feature-flagged PostgreSQL read-switch support for image/video benchmark datasets, suites, and runs.

Default runtime behavior remains JSON/file-only. Benchmark record reads prefer PostgreSQL only when the database is enabled and the `benchmark_records` read domain is explicitly selected. JSON fallback can be enabled for misses, empty project/suite lists, or PostgreSQL read errors.

## Runtime Flags

- `MIEMIE_DATABASE_ENABLED=true`
- `MIEMIE_DATABASE_READ_DOMAINS=benchmark_records` or `MIEMIE_DATABASE_READ_MODE=postgres`
- `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` falls back to JSON on PostgreSQL miss, empty list, or read error
- `MIEMIE_DATABASE_JSON_FALLBACK_READ=false` propagates PostgreSQL read errors and returns PostgreSQL misses/empty lists directly

## Changed Files

- `backend/app/repositories/benchmark_record_runtime.py`
- `backend/app/services/storage.py`
- `backend/tests/test_benchmark_record_read_switch.py`

## Verification

- RED gate: `backend/.venv/bin/pytest backend/tests/test_benchmark_record_read_switch.py -q`
  - Expected failure before implementation: missing `build_benchmark_record_read_repository`
- Focused green: `backend/.venv/bin/pytest backend/tests/test_benchmark_record_read_switch.py -q`
  - Result: `4 passed`
- Compile: `backend/.venv/bin/python -m py_compile backend/app/repositories/benchmark_record_runtime.py backend/app/services/storage.py backend/app/repositories/benchmark_records.py`
  - Result: passed
- Target set: `backend/.venv/bin/pytest backend/tests/test_benchmark_record_read_switch.py backend/tests/test_benchmark_record_dual_write.py backend/tests/test_benchmark_record_migration.py backend/tests/test_benchmark_record_repository.py backend/tests/test_benchmark_record_schema.py backend/tests/test_storage_service.py -q`
  - Result: `17 passed`
- Full backend: `backend/.venv/bin/pytest backend/tests -q`
  - Result: `362 passed`

## Notes

- No backend API response shape changed.
- No frontend behavior changed.
- No server state changed in this step.
- PostgreSQL-primary mode for benchmark records remains pending.
