# PostgreSQL R1/R2 Local Implementation Evidence

Run date: 2026-06-07

Scope:

- R1 Compose PostgreSQL infrastructure.
- R2 database configuration, health output, backup script, restore rehearsal script, and tests.
- Business reads/writes remain JSON-only by default.

## Implemented

- Added `postgres:16-alpine` service to `docker-compose.yml`.
- Added conservative PostgreSQL defaults for small staging memory:
  - `shared_buffers=128MB`
  - `max_connections=50`
  - `work_mem=4MB`
  - `maintenance_work_mem=64MB`
- Added database migration env flags to `api`, `worker`, and `worker-video`, but did not add `depends_on: postgres`.
- Added `backend/app/db/engine.py` with lazy database health helpers.
- Added `/api/health.database`.
- Added `backend/tests/test_database_health.py`.
- Added `scripts/postgres_backup.sh`.
- Added `scripts/postgres_restore_rehearsal.sh`.
- Added `SQLAlchemy`, `psycopg[binary]`, and `alembic` to `requirements.txt`.
- Added `backend/backups/` to `.gitignore`.

## Verification

- `backend/.venv/bin/pip install -r requirements.txt`: passed.
- `docker compose config`: passed with database disabled and no PostgreSQL password.
- `MIEMIE_POSTGRES_PASSWORD=local-dev-password docker compose config`: passed and rendered `postgres_data`.
- `backend/.venv/bin/pytest backend/tests/test_database_health.py -q`: `3 passed`.
- `backend/.venv/bin/pytest backend/tests/test_database_health.py backend/tests/test_runtime_observability.py backend/tests/test_docker_runtime.py -q`: `7 passed`.
- `backend/.venv/bin/pytest backend/tests/test_storage_service.py -q`: `1 passed`.
- `backend/.venv/bin/pytest backend/tests -q`: `238 passed`.
- `cd frontend && npm run typecheck`: passed.
- `cd frontend && npm run test:vite-chunks`: passed.
- `cd frontend && npm run build`: passed with existing Browserslist/chunk-size warnings only.
- `bash -n scripts/postgres_backup.sh`: passed.
- `bash -n scripts/postgres_restore_rehearsal.sh`: passed.
- Import smoke with `MIEMIE_DATABASE_ENABLED=false`: returned `{"configured": false, "ok": null}`.

## Not Verified Locally

- `docker compose up -d postgres` did not run locally because the Docker daemon was not available:
  - `Cannot connect to the Docker daemon at unix:///Users/zane/.docker/run/docker.sock. Is the docker daemon running?`

This is not treated as a code failure. Staging already has Docker running and `postgres:16-alpine` pulled, so R1/R2 rollout must verify container startup, `pg_isready`, backup, and restore rehearsal on the server.

## Sensitive Data

No raw key, token, PostgreSQL password, or private user data was written to this artifact.
