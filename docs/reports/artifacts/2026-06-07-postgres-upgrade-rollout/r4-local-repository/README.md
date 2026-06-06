# R4 Local Repository Boundary

## Scope

This artifact records the local R4 groundwork for `video_studio_tasks`.

Implemented:

- `backend/app/repositories/base.py` defines the repository mode, write error, and video studio task repository protocol.
- `backend/app/repositories/video_studio_tasks.py` adds:
  - file repository adapter over the existing JSON `StorageService`.
  - PostgreSQL row mapping with full `raw_task_snapshot` preservation.
  - PostgreSQL repository with upsert reads and soft-delete semantics.
  - dual repository that writes JSON primary first, then PostgreSQL shadow.
- `backend/tests/test_video_studio_task_repository.py` covers file-only behavior, row mapping, and dual-write shadow failure handling.

Not changed:

- No router or worker read/write switch was enabled in this slice.
- Runtime behavior remains JSON/file-only unless a future phase wires the repository into the route/worker paths.
- No live PostgreSQL migration was executed in this slice.

## Verification

```text
backend/.venv/bin/pytest backend/tests/test_video_studio_task_repository.py -q
4 passed in 0.97s

backend/.venv/bin/pytest backend/tests/test_video_studio_task_repository.py backend/tests/test_video_studio_task_schema.py backend/tests/test_database_health.py -q
10 passed in 0.81s

backend/.venv/bin/pytest backend/tests -q
245 passed in 63.75s
```

## Follow-Up

- Recover staging SSH/API verification and close R1/R2 rollout status.
- Run live `alembic upgrade head` after PostgreSQL container health is proven.
- Add backfill and reconcile scripts before enabling dual-write in runtime.
