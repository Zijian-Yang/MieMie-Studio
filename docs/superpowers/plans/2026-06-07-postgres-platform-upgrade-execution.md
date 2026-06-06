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
MIEMIE_DATABASE_READ_DOMAINS=
MIEMIE_DATABASE_JSON_FALLBACK_READ=true
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

- [ ] Add SQLAlchemy metadata for `video_studio_tasks`.
- [ ] Add partial indexes for `user_id/project_id/updated_at`, `user_id/status/updated_at`, and `submit_attempt_id`.
- [ ] Add migration upgrade/downgrade.
- [ ] Verify against a temporary PostgreSQL service.

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

- [ ] Define repository protocol: `save`, `get`, `list_for_project`, `delete`, `mark_deleted`.
- [ ] Implement file repository by wrapping current `StorageService` calls.
- [ ] Implement postgres repository using SQLAlchemy.
- [ ] Implement dual repository that writes JSON first, then PostgreSQL.
- [ ] Default mode remains file-only.
- [ ] Route and worker behavior is unchanged when env flags are disabled.

Required tests:

- file-only repository round-trips an existing `VideoStudioTask`.
- postgres repository round-trips JSONB fields.
- dual repository returns success only when JSON write succeeds.
- postgres failure in shadow mode is logged and does not break JSON primary path.

## Task R5: Backfill And Reconcile

**Files:**
- Create: `backend/app/services/migration/backfill_video_studio_tasks.py`
- Create: `backend/app/services/migration/reconcile_video_studio_tasks.py`
- Create: `scripts/postgres_backfill_video_studio_tasks.py`
- Create: `scripts/postgres_reconcile_video_studio_tasks.py`
- Create: `backend/tests/test_video_studio_task_migration.py`

- [ ] Backfill scans all per-user JSON video studio tasks and upserts PostgreSQL rows.
- [ ] Reconcile compares record counts, ids, `user_id`, `project_id`, `status`, `updated_at`, `submit_attempt_id`, and deleted state.
- [ ] Reconcile writes JSON + Markdown summaries.
- [ ] Summaries never include token, password, API key, prompt body, raw provider payload, or private URLs unless explicitly whitelisted for test fixtures.

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

- [ ] When `MIEMIE_DATABASE_READ_DOMAINS=video_studio_tasks`, list/status reads use PostgreSQL.
- [ ] If `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` and PostgreSQL misses a task, fallback to JSON and log a reconciliation warning.
- [ ] Rollback is `MIEMIE_DATABASE_READ_DOMAINS=` and `MIEMIE_DATABASE_WRITE_MODE=file`.
- [ ] Keep public API response shapes unchanged.

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

## Goal-Mode Operating Rule

Once goal mode starts, do not ask the user for routine information covered by this plan. Use these defaults:

- Use `root@47.79.99.190` and `/opt/miemie-pre`.
- Use public entry `https://pre-studio.miemie.co`.
- Use server-local entry `http://127.0.0.1:18100`.
- Use PostgreSQL service name `postgres`, database/user `miemie`, and a non-committed password in server `compose.env`.
- Keep JSON primary until a task explicitly switches read/write flags.
- For real provider tests, use only already configured server-side credentials; never ask the user to paste raw keys during automated execution.
- If a prerequisite is missing, write `status.json` with `"state": "blocked"` and the exact missing item.
