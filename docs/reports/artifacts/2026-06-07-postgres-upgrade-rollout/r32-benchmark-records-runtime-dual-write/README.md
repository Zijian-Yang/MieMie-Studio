# R32 Benchmark Records Runtime Dual-Write

## Summary

R32 adds feature-flagged PostgreSQL shadow writes for image/video benchmark datasets, suites, and runs.

Default runtime behavior remains file-only. `StorageService` still writes or deletes JSON first; PostgreSQL shadow writes run only when database support and the benchmark records dual-write domain are explicitly enabled.

## Runtime Flags

- `MIEMIE_DATABASE_ENABLED=true`
- `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=benchmark_records` or `MIEMIE_DATABASE_WRITE_MODE=dual|dual_write`
- `MIEMIE_DATABASE_RECONCILE_STRICT=false` keeps JSON primary writes successful when shadow writes fail
- `MIEMIE_DATABASE_RECONCILE_STRICT=true` propagates shadow write failures after the JSON primary write succeeds

## Changed Files

- `backend/app/repositories/benchmark_record_runtime.py`
- `backend/app/services/storage.py`
- `backend/tests/test_benchmark_record_dual_write.py`

## Verification

- RED gate: `backend/.venv/bin/pytest backend/tests/test_benchmark_record_dual_write.py -q`
  - Expected failure before implementation: missing `app.repositories.benchmark_record_runtime`
- Focused green: `backend/.venv/bin/pytest backend/tests/test_benchmark_record_dual_write.py -q`
  - Result: `4 passed`
- Compile: `backend/.venv/bin/python -m py_compile backend/app/repositories/benchmark_record_runtime.py backend/app/services/storage.py backend/app/repositories/benchmark_records.py`
  - Result: passed
- Target set: `backend/.venv/bin/pytest backend/tests/test_benchmark_record_dual_write.py backend/tests/test_benchmark_record_migration.py backend/tests/test_benchmark_record_repository.py backend/tests/test_benchmark_record_schema.py backend/tests/test_storage_service.py -q`
  - Result: `13 passed`
- Full backend: `backend/.venv/bin/pytest backend/tests -q`
  - Result: `358 passed`

## Notes

- No backend API response shape changed.
- No frontend behavior changed.
- No server state changed in this step.
- Read-switch and PostgreSQL-primary mode for benchmark records remain pending.
