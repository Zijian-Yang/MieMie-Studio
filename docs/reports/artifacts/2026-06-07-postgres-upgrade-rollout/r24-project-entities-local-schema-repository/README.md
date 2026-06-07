# R24 Project Entities Local Schema/Repository

## Scope

- Domain: `project_entities`
- Entity kinds:
  - `character`
  - `scene`
  - `prop`
  - `frame`
  - `video`
  - `style`
- Runtime default remains file-only.
- No server state, Nginx, Cloudflare, provider key, OSS object, or production data was changed in this local slice.

## Changes

- Added `backend/app/db/schema/project_entities.py`.
- Added Alembic migration `20260607_0005_project_entities`.
- Registered `project_entities` in shared SQLAlchemy metadata.
- Added `backend/app/repositories/project_entities.py` with:
  - row mapping into indexed columns
  - full `raw_entity_snapshot` JSONB preservation
  - file repository adapter over current `StorageService`
  - PostgreSQL repository boundary
  - dual repository boundary
- Added tests:
  - `backend/tests/test_project_entity_schema.py`
  - `backend/tests/test_project_entity_repository.py`

## Design Note

This slice uses a single `project_entities` table keyed by `(id, entity_kind)`. The table stores shared query/index columns plus a full JSONB snapshot. This keeps the first database boundary narrow while preserving enough indexed structure for project entity lists, shot-based frame/video lookups, and future per-kind extraction when the schema stabilizes.

## Verification

Commands run on 2026-06-07:

```bash
backend/.venv/bin/pytest backend/tests/test_project_entity_schema.py backend/tests/test_project_entity_repository.py -q
backend/.venv/bin/python -m py_compile backend/app/db/schema/project_entities.py backend/app/db/migrations/versions/20260607_0005_project_entities.py backend/app/repositories/project_entities.py
backend/.venv/bin/pytest backend/tests/test_project_entity_schema.py backend/tests/test_project_entity_repository.py backend/tests/test_project_repository.py backend/tests/test_media_metadata_repository.py backend/tests/test_storage_service.py -q
docker compose config
MIEMIE_DATABASE_URL=postgresql+psycopg://miemie:local@postgres:5432/miemie backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head --sql
backend/.venv/bin/pytest backend/tests -q
```

Result:

- RED collection gate failed before implementation with missing `project_entities` schema and repository modules.
- Focused project entity tests: `7 passed`.
- Schema/repository target: `16 passed`.
- Alembic offline SQL generated through revision `20260607_0005`.
- Full backend suite: `331 passed`.
- `py_compile` and `docker compose config` passed.

## Next

- Add project entity backfill/reconcile scripts.
- Then add runtime dual-write, read-switch, and primary-write for this domain.
- Server rollout remains blocked from the current operator path until SSH/public health is reliable.
