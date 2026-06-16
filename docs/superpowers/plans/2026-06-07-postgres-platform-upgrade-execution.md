# PostgreSQL Platform Upgrade Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the MieMie-Studio platform upgrade from JSON-only persistence to Compose PostgreSQL-backed core state with JSON transition, reconciliation, rollback, server rollout, and performance gates.

**Architecture:** Keep the current JSON storage path as the primary source during the first migration stages. Add PostgreSQL inside the existing Compose boundary, expose database health, add migrations, backfill and reconcile scripts, then migrate one domain at a time through shadow, dual-write, read-switch, PostgreSQL-primary, and JSON archive states.

**Tech Stack:** Docker Compose, PostgreSQL 16, FastAPI, SQLAlchemy 2.x, psycopg 3, Alembic, pytest, k6, Cloudflare/Nginx pre entry, existing Redis/Celery workers.

---

## Execution Assumptions

- Branch: `pre`.
- Local repo: `/Users/zane/Project/Miemie-studio-ha-lab`.
- Staging server: `root@47.79.99.190`.
- Staging app path: `/opt/miemie-pre`.
- Staging Compose project: `miemie-pre`.
- Public entry: `https://pre-studio.miemie.co`.
- Local server entry on staging: `http://127.0.0.1:18100`.
- Reverse proxy and Cloudflare remain user-managed; application changes must not require editing the aaPanel Nginx main config.
- Real provider tests may use an already configured server-side test key/profile. Do not write raw keys, passwords, tokens, or private user data to artifacts.
- If no provider key is configured, run preview/no-key failure-path smoke and record real-provider smoke as blocked by missing configured key, without asking for raw keys in the middle of goal execution.

## Roadmap

| Phase | Commit boundary | Runtime risk | Rollout target |
|---|---|---:|---|
| R0 Preflight | docs + artifact only | none | prove local/server prerequisites |
| R1 Compose PG infra | compose/env/docs | low | PostgreSQL container starts; API still file-only |
| R2 Health + backup | db health + scripts | low | `/api/health.database` observed; backup/restore rehearsed |
| R3 Alembic + task schema | migrations only | low | `video_studio_tasks` table exists; no business read/write switch |
| R4 Video task shadow | repository + tests | medium | JSON remains primary; PG backfill/reconcile works |
| R5 Dual-write | feature-flagged repository | medium | writes go JSON then PG; reads remain JSON |
| R6 Read switch | feature-flagged reads | medium | video task list/status can read PG with JSON fallback |
| R7 Server soak | rollout + S4/W2 gates | medium | staging validates health, reconcile, rollback, load |
| R8 Next domains | projects/media/etc. | medium/high | repeat same state machine per domain |

## State Files And Artifacts

- Preflight artifact dir: `docs/reports/artifacts/2026-06-07-postgres-upgrade-preflight/`
- Rollout artifact dir: `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/`
- Existing high-level plan: `docs/plans/2026-06-06-postgres-upgrade-optimization-plan.md`
- This executable plan: `docs/superpowers/plans/2026-06-07-postgres-platform-upgrade-execution.md`
- Stage report to maintain: `docs/reports/2026-05-24-next-phase-experience-and-performance.md`
- Active plan index to maintain: `docs/plans/2026-05-23-unfinished-work-implementation-plan.md`
- Docs entrypoint to maintain: `docs/README.md`
- Changelog to maintain: `docs/CHANGELOG.md`

## Stop Conditions

Stop the current phase immediately when any of these happen:

- Local tests fail after two focused fix attempts.
- `docker compose config` fails for the default local configuration.
- Staging `/api/health` returns non-200 before rollout.
- Staging `api`, `redis`, `worker`, or `worker-video` is missing or restarting unexpectedly before database rollout.
- PostgreSQL cannot be backed up and restored in a rehearsal directory.
- Reconciliation reports missing primary keys or field drift after backfill/dual-write.
- Any staging load gate produces 5xx amplification, container restarts, or data mismatch.

## Task R0: Preflight And Evidence Setup

**Files:**
- Create: `docs/reports/artifacts/2026-06-07-postgres-upgrade-preflight/README.md`
- Create: `docs/reports/artifacts/2026-06-07-postgres-upgrade-preflight/status.json`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/README.md`

- [x] **Step 1: Verify local git branch and clean state**

Run:

```bash
git branch --show-current
git status --short
git rev-parse HEAD
```

Expected:

```text
pre
<empty or only this task's docs after edits>
<current commit sha>
```

- [x] **Step 2: Verify local dependency surfaces**

Run:

```bash
docker --version
docker compose version
backend/.venv/bin/python --version
backend/.venv/bin/pytest --version
node --version
npm --version
k6 version
```

Expected: every command prints a version. If `k6` is missing locally, record it; server-side k6 may still be sufficient for staging gates.

- [x] **Step 3: Verify local static config gates**

Run:

```bash
docker compose config
backend/.venv/bin/pytest backend/tests/test_runtime_observability.py backend/tests/test_storage_service.py -q
cd frontend && npm run typecheck
cd frontend && npm run test:vite-chunks
```

Expected: all commands pass before code changes begin.

- [x] **Step 4: Verify staging SSH and runtime gates**

Run:

```bash
ssh -o StrictHostKeyChecking=accept-new root@47.79.99.190 'set -eu; cd /opt/miemie-pre; echo "## host"; hostname; echo "## git"; git rev-parse HEAD; echo "## files"; test -f compose.env && echo compose.env:ok; test -f docker-compose.yml && echo docker-compose.yml:ok; test -f docker-compose.pre.override.yml && echo docker-compose.pre.override.yml:ok; echo "## compose ps"; docker compose -p miemie-pre --env-file compose.env -f docker-compose.yml -f docker-compose.pre.override.yml ps; echo "## health-local"; curl -sS -D - -o /tmp/miemie-health.json --connect-timeout 5 --max-time 15 http://127.0.0.1:18100/api/health; echo; cat /tmp/miemie-health.json; echo; echo "## docker stats"; docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"'
```

Expected:

- SSH returns `0`.
- `compose.env`, `docker-compose.yml`, and `docker-compose.pre.override.yml` exist on server.
- `/api/health` status is `200`.
- Health body contains `status=ok`, `redis.ok=true`, and current runtime `git_commit`.
- `api`, `redis`, `worker`, and `worker-video` are running.

- [x] **Step 5: Verify public entry and Cloudflare headers**

Run:

```bash
curl --noproxy "*" -sS -D /tmp/pre-studio-public-health.headers -o /tmp/pre-studio-public-health.json --connect-timeout 10 --max-time 20 https://pre-studio.miemie.co/api/health
cat /tmp/pre-studio-public-health.headers
cat /tmp/pre-studio-public-health.json
```

Expected:

- HTTP status `200`.
- Headers include `server: cloudflare`, `x-request-id`, `x-deployment-version`, and `cf-cache-status: DYNAMIC`.

- [x] **Step 6: Write preflight artifact summary**

Create `docs/reports/artifacts/2026-06-07-postgres-upgrade-preflight/status.json` with this shape:

```json
{
  "state": "ready",
  "stage": "preflight",
  "local_branch": "pre",
  "local_commit": "<commit>",
  "server_commit": "<commit>",
  "server_health": "ok",
  "public_health": "ok",
  "missing_prerequisites": [],
  "updated_at": "2026-06-07T00:00:00+08:00"
}
```

Use `"state": "blocked"` and list exact missing prerequisites if any required gate fails.

- [x] **Step 7: Commit preflight docs and artifacts**

Run:

```bash
git add docs/superpowers/plans/2026-06-07-postgres-platform-upgrade-execution.md docs/reports/artifacts/2026-06-07-postgres-upgrade-preflight/ docs/README.md docs/CHANGELOG.md
git commit -m "docs: 落盘PostgreSQL升级执行路线"
git push origin pre
```

## Task R1: Add Compose PostgreSQL Infrastructure

**Files:**
- Modify: `docker-compose.yml`
- Modify: `compose.env.example`
- Modify: `docs/DEPLOYMENT.md`
- Modify: `docs/README.md`
- Modify: `docs/CHANGELOG.md`
- Artifact: `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r1-compose-infra/`

- [x] **Step 1: Add PostgreSQL service without making API depend on it**

Add `postgres` service:

```yaml
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: "${MIEMIE_POSTGRES_DB:-miemie}"
      POSTGRES_USER: "${MIEMIE_POSTGRES_USER:-miemie}"
      POSTGRES_PASSWORD: "${MIEMIE_POSTGRES_PASSWORD:?set MIEMIE_POSTGRES_PASSWORD}"
      TZ: "${TZ:-Asia/Shanghai}"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/backups/postgres:/backups
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
```

Add volume:

```yaml
  postgres_data:
```

Do not add `depends_on: postgres` to `api`, `worker`, or `worker-video` in this task.

- [x] **Step 2: Add env example defaults**

Add to `compose.env.example`:

```bash
# PostgreSQL：数据库升级阶段先默认关闭业务依赖。
MIEMIE_POSTGRES_DB=miemie
MIEMIE_POSTGRES_USER=miemie
# 必须在真实 compose.env 中设置强密码，不提交真实值。
MIEMIE_POSTGRES_PASSWORD=replace-with-strong-password
MIEMIE_DATABASE_ENABLED=false
MIEMIE_DATABASE_URL=postgresql+psycopg://miemie:${MIEMIE_POSTGRES_PASSWORD}@postgres:5432/miemie
MIEMIE_DATABASE_WRITE_MODE=file
MIEMIE_DATABASE_READ_MODE=file
MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=
MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=
MIEMIE_DATABASE_READ_DOMAINS=
MIEMIE_DATABASE_JSON_FALLBACK_READ=true
MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false
MIEMIE_DATABASE_RECONCILE_STRICT=false
```

- [x] **Step 3: Verify local Compose config**

Run:

```bash
MIEMIE_POSTGRES_PASSWORD=local-dev-password docker compose config
```

Expected: config renders successfully.

- [ ] **Step 4: Verify local PostgreSQL container starts**

2026-06-07 note: skipped locally because Docker daemon was not running (`Cannot connect to the Docker daemon at unix:///Users/zane/.docker/run/docker.sock`). Server preflight already pulled and executed `postgres:16-alpine`; R1/R2 rollout must complete this check on staging.

Run:

```bash
MIEMIE_POSTGRES_PASSWORD=local-dev-password docker compose up -d postgres
docker compose ps postgres
docker compose exec -T postgres pg_isready -U miemie -d miemie
```

Expected: `pg_isready` prints `accepting connections`.

- [x] **Step 5: Verify API still works with database disabled**

Run existing fast tests:

```bash
backend/.venv/bin/pytest backend/tests/test_docker_runtime.py backend/tests/test_runtime_observability.py -q
```

Expected: pass.

## Task R2: Database Config, Health, Backup, Restore

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/engine.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_database_health.py`
- Create: `scripts/postgres_backup.sh`
- Create: `scripts/postgres_restore_rehearsal.sh`
- Modify: `requirements.txt`
- Modify: `docs/DEPLOYMENT.md`

- [x] **Step 1: Add dependencies**

Add to `requirements.txt`:

```text
SQLAlchemy>=2.0.0
psycopg[binary]>=3.1.0
alembic>=1.13.0
```

- [x] **Step 2: Add database engine module**

Create `backend/app/db/engine.py` with these public functions and behavior:

```python
def database_enabled() -> bool:
    """Return true when MIEMIE_DATABASE_ENABLED is true/1/yes."""

def database_url_configured() -> bool:
    """Return true when MIEMIE_DATABASE_URL is non-empty."""

def sanitized_database_url() -> str | None:
    """Return a password-redacted URL for logs only, or None when missing."""

def database_health(timeout_seconds: float = 0.5) -> dict:
    """Return configured/ok/error status without leaking credentials."""
```

Required behavior:

- `database_enabled()` reads `MIEMIE_DATABASE_ENABLED`.
- If disabled, `database_health()` returns `{"configured": False, "ok": None}`.
- If enabled but URL is missing, return `{"configured": False, "ok": False, "error": "MissingDatabaseUrl"}`.
- If enabled and connection succeeds, return `{"configured": True, "ok": True}`.
- If enabled and connection fails, return `{"configured": True, "ok": False, "error": "<ExceptionClass>"}`.
- Never include password or full URL in health output.

- [x] **Step 3: Add health output**

Modify `/api/health` response to include:

```json
"database": {
  "configured": false,
  "ok": null
}
```

when database is disabled.

- [x] **Step 4: Test health behavior**

Add `backend/tests/test_database_health.py` covering:

- disabled database returns configured false and ok null.
- enabled with missing URL returns configured false and ok false.
- enabled with invalid URL returns configured true and ok false without leaking password.

Run:

```bash
backend/.venv/bin/pytest backend/tests/test_database_health.py -q
backend/.venv/bin/pytest backend/tests/test_runtime_observability.py backend/tests/test_docker_runtime.py -q
```

- [x] **Step 5: Add backup script**

Create `scripts/postgres_backup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-miemie-pre}"
ENV_FILE="${ENV_FILE:-compose.env}"
COMPOSE_FILE_1="${COMPOSE_FILE_1:-docker-compose.yml}"
COMPOSE_FILE_2="${COMPOSE_FILE_2:-docker-compose.pre.override.yml}"
BACKUP_DIR="${BACKUP_DIR:-backend/backups/postgres}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"
docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE_1" -f "$COMPOSE_FILE_2" exec -T postgres \
  sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > "$BACKUP_DIR/miemie-postgres-$TIMESTAMP.sql"
echo "$BACKUP_DIR/miemie-postgres-$TIMESTAMP.sql"
```

- [x] **Step 6: Add restore rehearsal script**

Create `scripts/postgres_restore_rehearsal.sh` that restores a dump into a temporary database named `miemie_restore_check`, runs `select 1`, and drops the temporary database. It must not overwrite production tables.

## Task R3: Alembic And Video Studio Task Schema

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/app/db/migrations/env.py`
- Create: `backend/app/db/migrations/versions/20260607_0001_video_studio_tasks.py`
- Create: `backend/app/db/schema/__init__.py`
- Create: `backend/app/db/schema/video_studio_tasks.py`
- Create: `backend/tests/test_video_studio_task_schema.py`

- [x] Add SQLAlchemy metadata for `video_studio_tasks`.
- [x] Add partial indexes for `user_id/project_id/updated_at`, `user_id/status/updated_at`, and `submit_attempt_id`.
- [x] Add migration upgrade/downgrade.
- [ ] Verify against a temporary PostgreSQL service.

2026-06-07 note: local schema tests and Alembic offline SQL generation pass. Live PostgreSQL migration is pending because local Docker daemon is unavailable and staging SSH/health verification is still not reliable after the R1/R2 build disconnect.

Run inside the Compose network, without exposing PostgreSQL on a host port:

```bash
docker compose --env-file compose.env exec -T api \
  /opt/venv/bin/python -m alembic -c backend/alembic.ini upgrade head
```

Expected: migration completes and `video_studio_tasks` exists.

## Task R4: Video Studio Shadow Repository

**Files:**
- Create: `backend/app/repositories/__init__.py`
- Create: `backend/app/repositories/base.py`
- Create: `backend/app/repositories/video_studio_tasks.py`
- Modify: `backend/app/routers/video_studio.py`
- Modify: `backend/app/worker_tasks.py`
- Create: `backend/tests/test_video_studio_task_repository.py`

- [x] Define repository protocol: `save`, `get`, `list_for_project`, `list_all`, `delete`, `mark_deleted`.
- [x] Implement file repository by wrapping current `StorageService` calls.
- [x] Implement postgres repository using SQLAlchemy.
- [x] Implement dual repository that writes JSON first, then PostgreSQL.
- [x] Default mode remains file-only.
- [x] Route and worker behavior is unchanged when env flags are disabled.

2026-06-07 note: local R4 repository boundary is implemented and covered by `backend/tests/test_video_studio_task_repository.py`; no router/worker wiring was enabled in this slice, so runtime remains JSON/file-only. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r4-local-repository/`. Live PostgreSQL validation is still pending staging SSH/API recovery.

Required tests:

- file-only repository round-trips an existing `VideoStudioTask`.
- postgres row mapping preserves indexed columns and JSONB `raw_task_snapshot`.
- dual repository returns success only when JSON write succeeds.
- postgres failure in shadow mode is logged and does not break JSON primary path.

## Task R5: Backfill And Reconcile

**Files:**
- Create: `backend/app/services/migration/backfill_video_studio_tasks.py`
- Create: `backend/app/services/migration/reconcile_video_studio_tasks.py`
- Create: `scripts/postgres_backfill_video_studio_tasks.py`
- Create: `scripts/postgres_reconcile_video_studio_tasks.py`
- Create: `backend/tests/test_video_studio_task_migration.py`

- [x] Backfill scans all per-user JSON video studio tasks and upserts PostgreSQL rows.
- [x] Reconcile compares record counts, ids, `project_id`, `status`, `updated_at`, and `submit_attempt_id` for scanned users.
- [x] Reconcile writes JSON + Markdown summaries.
- [x] Summaries never include token, password, API key, prompt body, raw provider payload, or private URLs unless explicitly whitelisted for test fixtures.

2026-06-07 note: local R5 backfill/reconcile tooling is implemented and covered by `backend/tests/test_video_studio_task_migration.py`; live backfill/reconcile is pending staging SSH/API recovery plus live `alembic upgrade head`. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r5-backfill-reconcile/`.

2026-06-07 note: runtime dual-write feature flag for `video_studio_tasks` is implemented as the local read-switch prerequisite. `StorageService.save_video_studio_task()` and `delete_video_studio_task()` remain JSON-primary, then shadow-write PostgreSQL only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=video_studio_tasks` or `MIEMIE_DATABASE_WRITE_MODE=dual`. Reads still remain JSON/file-only. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r6-runtime-dual-write/`.

Expected reconcile JSON:

```json
{
  "domain": "video_studio_tasks",
  "json_count": 0,
  "postgres_count": 0,
  "missing_in_postgres": [],
  "missing_in_json": [],
  "field_differences": [],
  "ok": true
}
```

## Task R6: Read Switch And Rollback

**Files:**
- Modify: `backend/app/repositories/video_studio_tasks.py`
- Modify: `backend/app/routers/video_studio.py`
- Create: `backend/tests/test_video_studio_task_read_switch.py`
- Modify: `docs/DEPLOYMENT.md`

- [x] When `MIEMIE_DATABASE_READ_DOMAINS=video_studio_tasks`, list/status reads use PostgreSQL.
- [x] If `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` and PostgreSQL misses a task, fallback to JSON and log a reconciliation warning.
- [x] Rollback is `MIEMIE_DATABASE_READ_DOMAINS=` and `MIEMIE_DATABASE_WRITE_MODE=file`.
- [x] Keep public API response shapes unchanged.

2026-06-07 note: local read switch and JSON fallback are implemented through `StorageService` video task read methods; runtime default remains file-only, and staging read switch is pending live migration/backfill/reconcile/dual-write evidence. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r6-read-switch/`.

2026-06-07 note: local PostgreSQL primary-write mode for `video_studio_tasks` is implemented as the next read-switch prerequisite. `StorageService.save_video_studio_task()` and `delete_video_studio_task()` route writes/deletes to PostgreSQL when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=video_studio_tasks` or `MIEMIE_DATABASE_WRITE_MODE=postgres_primary`; `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` keeps a temporary JSON mirror for audit/recovery. Runtime default remains file-only, and staging primary-write enablement is pending live migration/backfill/reconcile/dual-write/read-switch evidence. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r6-postgres-primary-write/`.

## Task R7: Staging Rollout Gate

**Files:**
- Create/update artifacts under `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/`
- Modify: `docs/reports/2026-05-24-next-phase-experience-and-performance.md`
- Modify: `docs/plans/2026-05-23-unfinished-work-implementation-plan.md`
- Modify: `docs/README.md`
- Modify: `docs/CHANGELOG.md`

- [ ] Server precheck: SSH, git commit, compose config, health, docker stats.
- [ ] Deploy PostgreSQL infra with DB disabled for API.
- [ ] Verify PostgreSQL container health.
- [ ] Verify `/api/health.database` with disabled, enabled, and failure cases.
- [ ] Run backup and restore rehearsal.
- [ ] Run migration upgrade.
- [ ] Run video task backfill and reconcile.
- [ ] Enable dual-write for `video_studio_tasks`.
- [ ] Create a disposable test user/project/task through public API.
- [ ] Reconcile after write.
- [ ] Enable read switch for `video_studio_tasks`.
- [ ] Re-run read/status gates from local app entry and public Cloudflare entry.
- [ ] Roll back read switch and prove JSON path works.

2026-06-07 note: R7 staging precheck was attempted after local R6 primary-write landed, but no server state was changed. The operator client path is currently intercepted by Clash TUN/fake-ip: `dig pre-studio.miemie.co` returned `198.18.2.211`, route to `47.79.99.190` used `utun1024`, SSH hit banner timeout/connection close, and public `/api/health` timed out even though TCP 22/443 connect checks succeeded. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r7-staging-precheck/`. Resume R7 only after stable SSH and public health are available.

## Task R8: Performance And Real Provider Gates

**Files:**
- Reuse: `loadtest/k6/s4-mixed-query-generate.js`
- Create/update artifacts under `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/`

- [ ] Run conservative S4 read gate locally and public:

```bash
K6_VUS=30 K6_DURATION=90s K6_SLEEP_SECONDS=2 k6 run loadtest/k6/s4-mixed-query-generate.js
```

- [ ] Run W2 status observation gate for the migrated read path:

```bash
K6_VUS=100 K6_DURATION=120s K6_SLEEP_SECONDS=1 k6 run loadtest/k6/s4-mixed-query-generate.js
```

- [ ] Run preview controlled-submit gate, not real supplier pressure:

```bash
K6_VUS=20 K6_DURATION=60s K6_SLEEP_SECONDS=1 MIEMIE_SUBMIT_EVERY=50 k6 run loadtest/k6/s4-mixed-query-generate.js
```

- [ ] If a server-side provider key/profile is already configured, run exactly one low-frequency real provider smoke after all no-real-provider gates pass.
- [ ] Delete test project and logout token.
- [ ] Do not delete test user by file operation unless separately approved.

## Task R9: Finish And Next Domain Decision

**Files:**
- Modify: `docs/plans/2026-06-06-postgres-upgrade-optimization-plan.md`
- Modify: `docs/plans/2026-05-23-unfinished-work-implementation-plan.md`
- Modify: `docs/reports/2026-05-24-next-phase-experience-and-performance.md`
- Modify: `docs/README.md`
- Modify: `docs/CHANGELOG.md`

- [ ] Record final database phase state.
- [ ] Record whether `video_studio_tasks` is file-only, dual-write, read-PG, or PG-primary.
- [ ] Record performance comparison before/after.
- [ ] Recommend the next domain: `studio_tasks`, then `projects`, then media metadata.
- [ ] Commit and push final docs/artifacts.

2026-06-07 note: while R7 staging precheck remained blocked by the operator-side TUN/fake-ip path, local next-domain work started. `studio_tasks` now has a PostgreSQL schema, Alembic migration `20260607_0002`, repository protocol, and file/PostgreSQL/dual repository boundary. Runtime remains file-only; backfill/reconcile and read/write feature flags are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r8-studio-tasks-local-schema-repository/`.

2026-06-07 note: local `studio_tasks` backfill/reconcile tooling is implemented and covered by `backend/tests/test_studio_task_migration.py`; summaries are sanitized and avoid prompt bodies, raw provider payloads, key/token/password values, and private URLs. Runtime remains file-only; dual-write, read-switch, and primary-write flags are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r9-studio-tasks-backfill-reconcile/`.

2026-06-07 note: local `studio_tasks` runtime dual-write is implemented through `backend/app/repositories/studio_task_runtime.py` and `StorageService.save_studio_task()` / `delete_studio_task()`. JSON remains primary; PostgreSQL shadow writes only run when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=studio_tasks` or `MIEMIE_DATABASE_WRITE_MODE=dual/dual_write`. Read-switch and primary-write flags are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r10-studio-tasks-runtime-dual-write/`.

2026-06-07 note: local `studio_tasks` read-switch and JSON fallback are implemented through `StorageService.get_studio_task()` and `get_studio_tasks_by_project()`. Reads prefer PostgreSQL only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_READ_DOMAINS=studio_tasks` or `MIEMIE_DATABASE_READ_MODE=postgres`; default remains file-only. Primary-write is still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r11-studio-tasks-read-switch/`.

2026-06-07 note: local `studio_tasks` PostgreSQL primary-write and optional JSON archive mirror are implemented through `StorageService.save_studio_task()` and `delete_studio_task()`. Writes use PostgreSQL primary only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=studio_tasks` or `MIEMIE_DATABASE_WRITE_MODE=postgres/postgres_primary/primary`; `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` keeps a temporary JSON archive mirror. PostgreSQL primary failures propagate and do not write JSON, avoiding split-brain during cutover. Runtime default remains file-only; staging enablement is pending live migration/backfill/reconcile/dual-write/read-switch evidence. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r12-studio-tasks-primary-write/`.

2026-06-07 note: local `projects` schema/repository boundary is implemented with Alembic revision `20260607_0003_projects`, `backend/app/db/schema/projects.py`, `ProjectRepository`, and file/PostgreSQL/dual repository implementations. The table stores list-query index columns plus `raw_project_snapshot` JSONB; runtime remains file-only. Backfill/reconcile, runtime dual-write, read-switch and primary-write are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r13-projects-local-schema-repository/`.

2026-06-07 note: local `projects` backfill/reconcile tooling is implemented through `backend/app/services/migration/backfill_projects.py`, `backend/app/services/migration/reconcile_projects.py`, `scripts/postgres_backfill_projects.py`, and `scripts/postgres_reconcile_projects.py`. Summaries are sanitized and avoid project names, descriptions, script contents, model config details, prompt bodies, key/token/password values, and private URLs. Runtime remains file-only; dual-write, read-switch, and primary-write flags are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r14-projects-backfill-reconcile/`.

2026-06-07 note: local `projects` runtime dual-write is implemented through `backend/app/repositories/project_runtime.py` and `StorageService.save_project()` / `delete_project()`. JSON remains primary; PostgreSQL shadow writes only run when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=projects` or `MIEMIE_DATABASE_WRITE_MODE=dual/dual_write`. Read-switch and primary-write flags are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r15-projects-runtime-dual-write/`.

2026-06-07 note: local `projects` read-switch and JSON fallback are implemented through `backend/app/repositories/project_runtime.py` and `StorageService.get_project()` / `list_projects()`. Reads prefer PostgreSQL only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_READ_DOMAINS=projects` or `MIEMIE_DATABASE_READ_MODE=postgres`; `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` falls back to JSON on miss, empty list, or PostgreSQL read error. Runtime default remains file-only, and primary-write is still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r16-projects-read-switch/`.

2026-06-07 note: local `projects` PostgreSQL primary-write and optional JSON archive mirror are implemented through `StorageService.save_project()` and `delete_project()`. Writes use PostgreSQL primary only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=projects` or `MIEMIE_DATABASE_WRITE_MODE=postgres/postgres_primary/primary`; `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` keeps a temporary JSON archive mirror. PostgreSQL primary failures propagate and do not write JSON, avoiding split-brain during cutover. Runtime default remains file-only; staging enablement is pending live migration/backfill/reconcile/dual-write/read-switch evidence. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r17-projects-primary-write/`.

2026-06-07 note: staging connectivity refresh remains blocked from the current operator path. SSH command execution returned `Connection closed by 47.79.99.190 port 22`, public `/api/health` timed out, DNS resolved `pre-studio.miemie.co` to fake-IP `198.18.2.211`, and route to `47.79.99.190` used `utun1024`; TCP 22 was reachable but insufficient for rollout automation. No server state was changed. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r18-staging-connectivity-refresh/`.

2026-06-07 note: local media metadata schema/repository boundary is implemented. `media_assets` covers gallery images, audio library items, and video library items with shared URL/metadata/index columns plus `raw_media_snapshot`; `text_items` covers text library content and versions with `raw_text_snapshot`. Alembic revision `20260607_0004` is added, runtime remains file-only, and backfill/reconcile plus read/write flags are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r19-media-metadata-local-schema-repository/`.

2026-06-07 note: local media metadata backfill/reconcile tooling is implemented through `backend/app/services/migration/backfill_media_metadata.py`, `backend/app/services/migration/reconcile_media_metadata.py`, `scripts/postgres_backfill_media_metadata.py`, and `scripts/postgres_reconcile_media_metadata.py`. Summaries are sanitized and compare only safe indexed fields; they avoid text contents, prompts, provider payloads, key/token/password values, and private URLs. Runtime remains file-only; dual-write, read-switch, primary-write, and frontend smoke are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r20-media-metadata-backfill-reconcile/`.

2026-06-07 note: local media metadata runtime dual-write is implemented through `backend/app/repositories/media_asset_runtime.py` and `StorageService` gallery/audio/video/text save/delete methods. JSON remains primary; PostgreSQL shadow writes only run when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=media_metadata` or `MIEMIE_DATABASE_WRITE_MODE=dual/dual_write`. Read-switch, primary-write, and frontend smoke are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r21-media-metadata-runtime-dual-write/`.

2026-06-07 note: local media metadata read-switch and JSON fallback are implemented through `backend/app/repositories/media_asset_runtime.py` and `StorageService` gallery/audio/video/text get/list methods. Reads prefer PostgreSQL only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_READ_DOMAINS=media_metadata` or `MIEMIE_DATABASE_READ_MODE=postgres`; `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` falls back to JSON on miss, empty list, or PostgreSQL read error. Runtime default remains file-only, and primary-write/frontend smoke are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r22-media-metadata-read-switch/`.

2026-06-07 note: local media metadata PostgreSQL primary-write and optional JSON archive mirror are implemented through `backend/app/repositories/media_asset_runtime.py` and `StorageService` gallery/audio/video/text save/delete methods. Writes use PostgreSQL primary only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=media_metadata` or `MIEMIE_DATABASE_WRITE_MODE=postgres/postgres_primary/primary`; `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` keeps a temporary JSON archive mirror. PostgreSQL primary failures propagate and do not write JSON, avoiding split-brain during cutover. Runtime default remains file-only; frontend smoke and staging enablement are pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r23-media-metadata-primary-write/`.

2026-06-07 note: local project editing entity schema/repository boundary is implemented. `project_entities` covers `character`, `scene`, `prop`, `frame`, `video`, and `style` with shared index columns plus `raw_entity_snapshot`; Alembic revision `20260607_0005` is added, runtime remains file-only, and backfill/reconcile plus read/write flags are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r24-project-entities-local-schema-repository/`.

2026-06-07 note: local project editing entity backfill/reconcile tooling is implemented through `backend/app/services/migration/backfill_project_entities.py`, `backend/app/services/migration/reconcile_project_entities.py`, `scripts/postgres_backfill_project_entities.py`, and `scripts/postgres_reconcile_project_entities.py`. Summaries are sanitized and compare only safe indexed fields; they avoid names, descriptions, prompts, text style bodies, provider task ids, key/token/password values, and private URLs. Runtime remains file-only; dual-write, read-switch, primary-write, and frontend smoke are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r25-project-entities-backfill-reconcile/`.

2026-06-07 note: local project editing entity runtime dual-write is implemented through `backend/app/repositories/project_entity_runtime.py` and `StorageService` character/scene/prop/frame/video/style save/delete methods. JSON remains primary; PostgreSQL shadow writes only run when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=project_entities` or `MIEMIE_DATABASE_WRITE_MODE=dual/dual_write`. Read-switch, primary-write, and frontend smoke are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r26-project-entities-runtime-dual-write/`.

2026-06-07 note: local project editing entity read-switch and JSON fallback are implemented through `backend/app/repositories/project_entity_runtime.py` and `StorageService` character/scene/prop/frame/video/style get/list methods plus frame/video by-shot and video by-task helpers. Reads prefer PostgreSQL only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_READ_DOMAINS=project_entities` or `MIEMIE_DATABASE_READ_MODE=postgres`; `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` falls back to JSON on miss, empty list, or PostgreSQL read error. Primary-write and frontend smoke are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r27-project-entities-read-switch/`.

2026-06-07 note: local project editing entity PostgreSQL primary-write and optional JSON archive mirror are implemented through `backend/app/repositories/project_entity_runtime.py` and `StorageService` character/scene/prop/frame/video/style save/delete methods. Writes use PostgreSQL primary only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=project_entities` or `MIEMIE_DATABASE_WRITE_MODE=postgres/postgres_primary/primary`; `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` keeps a temporary JSON archive mirror. PostgreSQL primary failures propagate and do not write JSON, avoiding split-brain during cutover. Runtime default remains file-only; frontend smoke and staging enablement are pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r28-project-entities-primary-write/`.

2026-06-07 note: R29 staging connectivity refresh still blocks server rollout from the current operator path. DNS for `pre-studio.miemie.co` returned fake-IP `198.18.2.211`, route to `47.79.99.190` used `utun1024`, public `/api/health` timed out, and SSH command execution was closed by the remote host despite TCP 22 being reachable. No server state was changed. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r29-staging-connectivity-refresh/`. Continue local benchmark/user/config migration work until SSH command execution and public health are both stable.

2026-06-07 note: local benchmark records schema/repository boundary is implemented with Alembic revision `20260607_0006_benchmark_records`, `backend/app/db/schema/benchmark_records.py`, and `backend/app/repositories/benchmark_records.py`. The table covers image/video benchmark dataset/suite/run records with safe index columns plus `raw_record_snapshot` JSONB. Runtime remains file-only; backfill/reconcile, dual-write, read-switch, and primary-write are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r30-benchmark-records-local-schema-repository/`.

2026-06-07 note: local benchmark records backfill/reconcile tooling is implemented through `backend/app/services/migration/backfill_benchmark_records.py`, `backend/app/services/migration/reconcile_benchmark_records.py`, `scripts/postgres_backfill_benchmark_records.py`, and `scripts/postgres_reconcile_benchmark_records.py`. Summaries are sanitized and avoid prompts, provider payloads, canonical request bodies, request ids, task ids, key/token/password values, private URLs, names, and descriptions. Runtime remains file-only; dual-write, read-switch, and primary-write are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r31-benchmark-records-backfill-reconcile/`.

2026-06-07 note: local benchmark records runtime dual-write is implemented through `backend/app/repositories/benchmark_record_runtime.py` and `StorageService` image/video benchmark dataset/suite/run save/delete methods. JSON remains primary; PostgreSQL shadow writes only run when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=benchmark_records` or `MIEMIE_DATABASE_WRITE_MODE=dual/dual_write`. Shadow failures default to warning-only, while `MIEMIE_DATABASE_RECONCILE_STRICT=true` propagates them after the JSON write succeeds. Read-switch and primary-write remain pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r32-benchmark-records-runtime-dual-write/`.

2026-06-07 note: local benchmark records read-switch and JSON fallback are implemented through `backend/app/repositories/benchmark_record_runtime.py` and `StorageService` image/video benchmark dataset/suite/run get/list methods. Reads prefer PostgreSQL only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_READ_DOMAINS=benchmark_records` or `MIEMIE_DATABASE_READ_MODE=postgres`; `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` falls back to JSON on miss, empty project/suite list, or PostgreSQL read error. Primary-write remains pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r33-benchmark-records-read-switch/`.

2026-06-07 note: local benchmark records PostgreSQL primary-write and optional JSON archive mirror are implemented through `backend/app/repositories/benchmark_record_runtime.py` and `StorageService` image/video benchmark dataset/suite/run save/delete methods. Writes use PostgreSQL primary only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=benchmark_records` or `MIEMIE_DATABASE_WRITE_MODE=postgres/postgres_primary/primary`; `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` keeps a temporary JSON archive mirror. PostgreSQL primary failures propagate and do not write JSON, avoiding split-brain during cutover. Runtime default remains file-only; staging enablement is pending live migration/backfill/reconcile/dual-write/read-switch evidence. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r34-benchmark-records-primary-write/`.

2026-06-07 note: local user/config schema/repository boundary is implemented with Alembic revision `20260607_0007_user_config`, `backend/app/db/schema/user_config.py`, and `backend/app/repositories/user_config.py`. `users` stores account index columns plus `password_hash` and `raw_user_snapshot`; `user_configs` stores safe indexes (`api_region`, `has_dashscope_key`, `has_oss_config`) plus `raw_config_snapshot`. Runtime remains JSON/Redis/file-only; `UserService`, sessions, and `ConfigManager` are not switched yet. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r35-user-config-local-schema-repository/`.

2026-06-07 note: local user/config backfill and reconcile tooling is implemented through `backend/app/services/migration/backfill_user_config.py`, `backend/app/services/migration/reconcile_user_config.py`, `scripts/postgres_backfill_user_config.py`, and `scripts/postgres_reconcile_user_config.py`. Summaries are sanitized and avoid password hash values, raw keys, tokens, full config snapshots, sessions, and private user data. Runtime remains JSON/Redis/file-only; dual-write/read-switch/primary-write flags are still pending. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r36-user-config-backfill-reconcile/`.

2026-06-07 note: local user/config runtime dual-write is implemented through `backend/app/repositories/user_config_runtime.py`, `UserService` register/login/password-change save paths, and `ConfigManager.save()`. JSON remains primary; PostgreSQL shadow writes only run when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=user_config` or global dual-write mode is explicitly enabled. Sessions remain Redis + file fallback. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r37-user-config-runtime-dual-write/`.

2026-06-07 note: local user/config read-switch and JSON fallback are implemented through `backend/app/repositories/user_config_runtime.py`, `UserService.get_user_by_id()`, token user recovery, and `ConfigManager.load()`. Reads prefer PostgreSQL only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_READ_DOMAINS=user_config` or global read mode is explicitly enabled; `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` falls back to JSON on miss/error. Login password verification remains JSON primary in this step. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r38-user-config-read-switch/`.

2026-06-07 note: local user/config PostgreSQL primary-write and optional JSON archive mirror are implemented through `backend/app/repositories/user_config_runtime.py`, `UserService` register/login/password-change paths, and `ConfigManager.save()`. Writes use PostgreSQL primary only when `MIEMIE_DATABASE_ENABLED=true` and `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=user_config` or global primary mode is explicitly enabled; `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` keeps a temporary JSON archive mirror. PostgreSQL primary failures propagate and do not write JSON. Sessions remain Redis + file fallback. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r39-user-config-primary-write/`.

2026-06-07 note: R40 staging connectivity refresh remains blocked from the current operator path after user/config local gates. DNS for `pre-studio.miemie.co` returned fake-IP `198.18.2.211`, route to `47.79.99.190` used `utun1024`, TCP 22 succeeded, SSH command execution timed out during banner exchange, and public `/api/health` timed out after 20 seconds. No server state was changed. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r40-staging-connectivity-after-user-config/`.

2026-06-07 note: R41 adds `scripts/postgres_live_rehearsal.sh`, a repeatable local live database rehearsal gate. The script creates a temporary non-committed Compose env and host-port override, starts PostgreSQL, runs `alembic upgrade head`, executes all domain backfill/reconcile scripts, and rehearses backup/restore. The current local run stopped at `docker-precheck` because the Docker daemon is unavailable; no business data, server state, raw password, token, key, or private user data was modified or written to artifacts. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r41-local-live-database-rehearsal/`.

2026-06-16 note: R42 resumed staging live rollout after SSH temporarily recovered. The server repo fast-forwarded from `cb2d4ff` to `e731245`, `postgres` started successfully, `pg_isready` accepted connections, and existing server-local/public health stayed `200`. While building the latest `api` image for one-off Alembic/backfill/reconcile execution, SSH command execution timed out during banner exchange again. No Alembic migration, backfill/reconcile, API restart, or database business switch was executed after that point. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r42-staging-postgres-live-resume/`.

2026-06-16 note: R43 completed staging live database gates without switching application traffic. A temporary server-side maintenance venv ran Alembic to `20260607_0007`, all domain backfill/reconcile scripts returned `ok=true`, PostgreSQL backup/restore rehearsal passed, and server-local/public health remained `200`. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r43-staging-live-migration-backfill-reconcile/`.

2026-06-16 note: R44 attempted to start the first application-level dual-write canary for `video_studio_tasks`, but stopped before any canary traffic. The server `compose.env` was backed up, `MIEMIE_RUNTIME_GIT_COMMIT` was updated to `e731245`, and `MIEMIE_DATABASE_ENABLED` stayed `false`. A `miemie-studio:pre-local` build was started, then the SSH session timed out before build completion was observed; follow-up SSH attempts timed out during banner exchange while the local route used `utun1024` / fake-IP. No container restart, no database business switch, and no dual-write canary occurred. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r44-staging-dual-write-canary-interrupted/`.

2026-06-17 note: R45 added `scripts/postgres_staging_video_task_canary.sh` to make the R44 recovery and first canary repeatable. The script has explicit `audit`, `roll-runtime`, and `dual-write-canary` modes. The canary write smoke uses an in-container `StorageService.save_video_studio_task()` maintenance write and direct PostgreSQL repository check, avoiding real provider calls; API smoke uses `preview-payload` only. Local verification passed `bash -n`, and a no-`compose.env` dry precheck exited blocked as expected. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r45-staging-canary-automation-script/`.

2026-06-17 note: R46 added `scripts/verify_postgres_staging_canary_script.py` as an app-free local verifier for the R45 shell script. It checks shell syntax, missing-env blocked precheck, no Docker touch before precheck, default read-only audit mode, runtime-disabled database switches, single-domain dual-write canary scope, no-provider smoke usage, and redaction markers. Server execution remains pending SSH banner recovery; no container restart or database business switch occurred. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r46-staging-canary-verifier/`.

2026-06-17 note: R47/R48 reran the local live database rehearsal after Docker daemon access was available outside the sandbox. R47 found the root cause of a false backup failure: `postgres_backup.sh` writes `.sql`, while `postgres_live_rehearsal.sh` searched for `*.dump`. R48 fixed the lookup and passed temporary Compose PostgreSQL startup, Alembic upgrade head, all-domain backfill/reconcile, `.sql` backup, restore rehearsal, and cleanup. Raw local outputs were not committed because they include local user UUIDs; sanitized summaries are archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r47-local-live-database-rehearsal-failed/` and `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r48-local-live-database-rehearsal/`.

2026-06-17 note: R49 extended `scripts/postgres_staging_video_task_canary.sh` with `read-switch-canary` and `rollback-read-switch` modes. The read-switch gate enables `MIEMIE_DATABASE_READ_DOMAINS=video_studio_tasks` and proves PostgreSQL is the read source by creating divergent JSON/PG canary task states; rollback clears read domains and proves JSON reads with the same divergent-source pattern. The verifier now compiles every embedded Python heredoc block. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r49-staging-read-switch-rollback-automation/`.

2026-06-17 note: R50 extended `scripts/postgres_staging_video_task_canary.sh` with `primary-write-canary` and `rollback-primary-write` modes. The primary-write gate enables `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=video_studio_tasks` plus read domains and proves PostgreSQL primary writes with no JSON archive file; rollback clears primary/read domains and proves JSON primary writes plus PostgreSQL shadow writes. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r50-staging-primary-write-rollback-automation/`.

2026-06-17 note: R51 retried the staging command path and still hit SSH banner timeout before remote execution while TCP 22 succeeded and local DNS/route remained fake-IP/TUN (`198.18.2.63`, `utun1024`). No server state changed. R51 added `scripts/postgres_staging_video_task_sequence.sh`, a default dry-run sequence runner that executes the full `audit -> roll-runtime -> dual-write-canary -> read-switch-canary -> rollback-read-switch -> primary-write-canary -> rollback-primary-write` chain only when `CONFIRM_STAGING_SEQUENCE=run`, stopping on the first non-zero stage. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r51-staging-sequence-runner-and-connectivity/`.

2026-06-17 note: R52 added `scripts/pre_studio_connectivity_preflight.sh` and `scripts/verify_pre_studio_connectivity_preflight.py` so the local operator path is checked before any R51 staging sequence. The live preflight is blocked: DNS resolves to fake-IP `198.18.0.80`, route to the origin uses gateway `198.18.0.1` and interface `utun1024`, TCP 22 is reachable, SSH banner closes, and public health returns an HTTP/2 framing error. No server state changed. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r52-connectivity-preflight/`.

2026-06-17 note: R53 added `scripts/pre_studio_remote_postgres_sequence.sh` and `scripts/verify_pre_studio_remote_postgres_sequence.py`, a local wrapper that runs R52 preflight first, then SSHes to `/opt/miemie-pre`, performs `git merge --ff-only origin/pre`, and runs `CONFIRM_STAGING_SEQUENCE=run scripts/postgres_staging_video_task_sequence.sh`. A confirmed live wrapper run stopped at local preflight and did not execute remote commands while the path remained fake-IP/TUN blocked. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r53-remote-postgres-sequence/`.

2026-06-17 note: R58 confirmed that another local DIRECT rule still does not clean the command-line path: DNS remains `198.18.0.100`, route remains `utun1024`, SSH banner times out, and public health times out. R58 adds `scripts/pre_studio_server_postgres_sequence.sh` and `scripts/verify_pre_studio_server_postgres_sequence.py` as a server-terminal fallback. When run from `/opt/miemie-pre` with `CONFIRM_SERVER_SEQUENCE=run`, it verifies the server context, syncs `origin/pre` with `git merge --ff-only`, and executes `CONFIRM_STAGING_SEQUENCE=run scripts/postgres_staging_video_task_sequence.sh`. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r58-connectivity-after-direct-rule/` and `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r58-server-self-sequence-wrapper/`.

2026-06-17 note: R59 adds the local PostgreSQL foundation for sessions without switching runtime auth. `sessions` schema and Alembic revision `20260607_0008` are added, `PostgresSessionRepository` stores only SHA-256 `token_hash`, and sanitized backfill/reconcile scripts compare `sessions.json` with PostgreSQL without writing raw tokens to artifacts. `scripts/postgres_live_rehearsal.sh` now includes the `sessions` domain after user/config. Local verification passed focused session tests, database schema/repository/migration targets, auth/session targets, full backend pytest (`408 passed`), py_compile, shell syntax, and Alembic offline SQL. A fresh connectivity preflight after another local DIRECT rule is still blocked with DNS `198.18.0.124`, route `utun1024`, SSH banner timeout, and public health timeout; no server sequence or business switch ran. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r59-sessions-local-schema-repository/` and `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r59-connectivity-after-direct-rule/`.

2026-06-17 note: R60 adds opt-in sessions runtime dual-write without changing default auth behavior. `backend/app/repositories/session_runtime.py` gates shadow saves/deletes behind `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=sessions` or global dual-write mode; `UserService` now shadow-saves on login, shadow-deletes on logout, and shadow-deletes all user sessions after password change. Shadow failures remain warning-only unless `MIEMIE_DATABASE_RECONCILE_STRICT=true`; raw tokens are not logged. Local verification passed focused R60 tests (`5 passed`), auth/session target (`63 passed`), database schema/repository/migration target (`87 passed`), full backend pytest (`413 passed`), and py_compile. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r60-sessions-runtime-dual-write/`.

2026-06-17 note: R61 adds opt-in sessions read-switch without changing default auth behavior. `session_runtime.read_session()` prefers PostgreSQL only when `MIEMIE_DATABASE_READ_DOMAINS=sessions` or global PostgreSQL read mode is enabled; `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` falls back to the current Redis/file session path on miss/error. Local verification passed focused R61 tests (`4 passed`), combined sessions runtime tests (`18 passed`), auth/session target (`67 passed`), database schema/repository/migration target (`91 passed`), and py_compile. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r61-sessions-read-switch/`.

2026-06-17 note: R62 rechecked the local operator path after another Clash direct-rule change. The network-scope preflight still blocks because DNS returns fake-IP `198.18.0.124` and the origin route uses gateway `198.18.0.1` / interface `utun1024`. Manual TCP 22 succeeds, but SSH command execution still times out during banner exchange after the TCP connection is established. No remote PostgreSQL sequence was executed and no server state changed. Evidence is archived in `docs/reports/artifacts/2026-06-17-postgres-connectivity-direct-rule/`.

2026-06-17 note: R63 adds opt-in sessions primary-write without changing default auth behavior. When `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=sessions` or global PostgreSQL write mode is enabled, session save/delete/user-session cleanup use PostgreSQL primary first; Redis remains a cache after primary save, `sessions.json` is only maintained with `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true`, and primary-write implies PostgreSQL reads. Local verification passed focused R63 tests (`7 passed`), sessions runtime combined (`25 passed`), auth/session target (`74 passed`), database schema/repository/migration target (`98 passed`), full backend pytest (`424 passed`), and py_compile. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r63-sessions-primary-write/`.

2026-06-17 note: R64 adds `scripts/postgres_staging_live_data_gate.sh` plus `scripts/verify_postgres_staging_live_data_gate.py`, and inserts `live-data-gate` into `scripts/postgres_staging_video_task_sequence.sh` after `roll-runtime`. The gate is dry-run by default; confirmed server execution runs Alembic head, all-domain backfill/reconcile, PostgreSQL backup, and restore rehearsal before any app-level dual-write/read-switch/primary-write canary. Local verification passed both live-data-gate and sequence verifiers plus py_compile. A fresh SSH check after another direct-rule change still timed out during banner exchange while route used `utun1024`, so no server sequence or business switch ran. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r64-staging-live-data-gate/` and `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r64-staging-sequence-with-live-data-gate/`.

2026-06-17 note: R65 tightens the blocked operator-path handoff. `scripts/pre_studio_connectivity_preflight.sh` now emits an exact `IP-CIDR,47.79.99.190/32,DIRECT,no-resolve` recommendation when the route is captured by a wide TUN range such as `32.0.0.0/3`. `scripts/pre_studio_server_postgres_sequence.sh` now verifies that the sequence runner includes `live-data-gate` and that `scripts/postgres_staging_live_data_gate.sh` exists. Live network-scope evidence still shows DNS `198.18.0.124` and route `32.0.0.0/3 -> 198.18.0.1 -> utun1024`, so no server sequence or business switch ran. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r65-connectivity-ip-cidr-remediation/` and `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r65-server-sequence-live-data-gate-contract/`.

2026-06-17 note: R66 aligns the local remote PostgreSQL wrapper with the server-terminal fallback. `scripts/pre_studio_remote_postgres_sequence.sh` still performs local connectivity preflight and remote `git merge --ff-only origin/pre`, but now invokes `CONFIRM_SERVER_SEQUENCE=run SERVER_SYNC=none scripts/pre_studio_server_postgres_sequence.sh` on the server. This keeps the local remote path and direct server-terminal path on the same live-data/canary/rollback contract. Evidence is archived in `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r66-remote-wrapper-server-fallback/`.

## Goal-Mode Operating Rule

Once goal mode starts, do not ask the user for routine information covered by this plan. Use these defaults:

- Use `root@47.79.99.190` and `/opt/miemie-pre`.
- Use public entry `https://pre-studio.miemie.co`.
- Use server-local entry `http://127.0.0.1:18100`.
- Use PostgreSQL service name `postgres`, database/user `miemie`, and a non-committed password in server `compose.env`.
- Keep JSON primary until a task explicitly switches read/write flags.
- For real provider tests, use only already configured server-side credentials; never ask the user to paste raw keys during automated execution.
- If a prerequisite is missing, write `status.json` with `"state": "blocked"` and the exact missing item.
- If the local operator path remains fake-IP/TUN blocked, run the server fallback from `/opt/miemie-pre`: `CONFIRM_SERVER_SEQUENCE=run scripts/pre_studio_server_postgres_sequence.sh`. The sequence now includes `live-data-gate` before app-level canaries.
