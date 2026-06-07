#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-postgres-live-rehearsal-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r41-local-live-database-rehearsal}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
PROJECT_NAME="${PROJECT_NAME:-miemie-postgres-rehearsal}"
HOST_PORT="${MIEMIE_POSTGRES_HOST_PORT:-15432}"
PYTHON_BIN="${PYTHON_BIN:-backend/.venv/bin/python}"
DATA_ROOT="${DATA_ROOT:-$ROOT_DIR/backend/data}"
KEEP_REHEARSAL_DB="${KEEP_REHEARSAL_DB:-false}"
if [[ -x "$PYTHON_BIN" ]]; then
  JSON_PYTHON="$PYTHON_BIN"
elif command -v python3 >/dev/null 2>&1; then
  JSON_PYTHON="python3"
else
  JSON_PYTHON=""
fi

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

COMMAND_LOG="$ARTIFACT_DIR/commands.log"
STATUS_FILE="$ARTIFACT_DIR/status.json"
ENV_FILE="$TMP_DIR/compose.env"
OVERRIDE_FILE="$TMP_DIR/docker-compose.postgres-host.override.yml"
BACKUP_DIR="$TMP_DIR/backups"
: > "$COMMAND_LOG"

STATE="running"
STAGE="init"
REASON=""

json_escape() {
  if [[ -n "$JSON_PYTHON" ]]; then
    printf '%s' "$1" | "$JSON_PYTHON" -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
  else
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
  fi
}

write_status() {
  local state="$1"
  local stage="$2"
  local reason="$3"
  cat > "$STATUS_FILE" <<JSON
{
  "run_id": "$(json_escape "$RUN_ID")",
  "state": "$(json_escape "$state")",
  "stage": "$(json_escape "$stage")",
  "reason": "$(json_escape "$reason")",
  "artifact_dir": "$(json_escape "$ARTIFACT_DIR")",
  "tmp_dir": "$(json_escape "$TMP_DIR")",
  "project_name": "$(json_escape "$PROJECT_NAME")",
  "postgres_host": "127.0.0.1",
  "postgres_host_port": "$(json_escape "$HOST_PORT")",
  "keep_rehearsal_db": "$(json_escape "$KEEP_REHEARSAL_DB")",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
}

run_logged() {
  local label="$1"
  shift
  STAGE="$label"
  write_status "$STATE" "$STAGE" ""
  {
    printf '\n## [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$label"
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  } >> "$COMMAND_LOG"
  "$@" >> "$COMMAND_LOG" 2>&1
}

redact_stream() {
  if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then
    sed "s/${POSTGRES_PASSWORD}/<redacted>/g"
  else
    cat
  fi
}

run_logged_redacted() {
  local label="$1"
  shift
  local raw_output="$TMP_DIR/${label}.raw.log"
  STAGE="$label"
  write_status "$STATE" "$STAGE" ""
  {
    printf '\n## [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$label"
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  } >> "$COMMAND_LOG"
  "$@" > "$raw_output" 2>&1
  redact_stream < "$raw_output" >> "$COMMAND_LOG"
}

mark_blocked() {
  STATE="blocked"
  STAGE="$1"
  REASON="$2"
  write_status "$STATE" "$STAGE" "$REASON"
  printf 'blocked: %s\n' "$REASON" | tee -a "$COMMAND_LOG" >&2
  exit 2
}

mark_failed() {
  STATE="failed"
  STAGE="$1"
  REASON="$2"
  write_status "$STATE" "$STAGE" "$REASON"
  printf 'failed: %s\n' "$REASON" | tee -a "$COMMAND_LOG" >&2
  exit 1
}

cleanup() {
  local exit_code=$?
  if [[ "$KEEP_REHEARSAL_DB" != "true" && -f "$ENV_FILE" && -f "$OVERRIDE_FILE" ]]; then
    docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" down -v >> "$COMMAND_LOG" 2>&1 || true
  fi
  if [[ "$exit_code" -ne 0 ]]; then
    return "$exit_code"
  fi
}
trap cleanup EXIT

write_status "$STATE" "$STAGE" ""

if [[ ! -x "$PYTHON_BIN" ]]; then
  mark_blocked "python-precheck" "Python venv is unavailable at $PYTHON_BIN"
fi

if ! command -v docker >/dev/null 2>&1; then
  mark_blocked "docker-precheck" "docker CLI is unavailable"
fi

if ! docker info >/dev/null 2>"$ARTIFACT_DIR/docker-info.err"; then
  mark_blocked "docker-precheck" "docker daemon unavailable; see docker-info.err"
fi

if ! docker compose version > "$ARTIFACT_DIR/docker-compose-version.txt" 2>&1; then
  mark_blocked "docker-compose-precheck" "docker compose is unavailable"
fi

if command -v openssl >/dev/null 2>&1; then
  POSTGRES_PASSWORD="$(openssl rand -hex 24)"
else
  POSTGRES_PASSWORD="rehearsal-$(date +%s)-$RANDOM"
fi

cat > "$ENV_FILE" <<ENV
MIEMIE_HOST_BIND=127.0.0.1
MIEMIE_HOST_PORT=8000
MIEMIE_WORKERS=1
MIEMIE_RUNTIME_GIT_COMMIT=$(git rev-parse HEAD 2>/dev/null || printf unknown)
MIEMIE_CORS_ORIGINS=
MIEMIE_REDIS_URL=redis://redis:6379/0
MIEMIE_RATE_LIMIT_STORAGE_URI=redis://redis:6379/1
MIEMIE_REDIS_KEY_PREFIX=miemie
MIEMIE_TASK_DISPATCHER=celery
MIEMIE_CELERY_BROKER_URL=redis://redis:6379/2
MIEMIE_CELERY_RESULT_BACKEND=redis://redis:6379/3
MIEMIE_WORKER_CONCURRENCY=1
MIEMIE_STUDIO_GENERATION_STALE_SECONDS=1800
MIEMIE_POSTGRES_DB=miemie
MIEMIE_POSTGRES_USER=miemie
MIEMIE_POSTGRES_PASSWORD=$POSTGRES_PASSWORD
MIEMIE_POSTGRES_SHARED_BUFFERS=128MB
MIEMIE_POSTGRES_MAX_CONNECTIONS=50
MIEMIE_POSTGRES_WORK_MEM=4MB
MIEMIE_POSTGRES_MAINTENANCE_WORK_MEM=64MB
MIEMIE_DATABASE_ENABLED=true
MIEMIE_DATABASE_URL=postgresql+psycopg://miemie:$POSTGRES_PASSWORD@postgres:5432/miemie
MIEMIE_DATABASE_WRITE_MODE=file
MIEMIE_DATABASE_READ_MODE=file
MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=
MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=
MIEMIE_DATABASE_READ_DOMAINS=
MIEMIE_DATABASE_JSON_FALLBACK_READ=true
MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false
MIEMIE_DATABASE_RECONCILE_STRICT=true
TZ=Asia/Shanghai
ENV
chmod 600 "$ENV_FILE"

cat > "$OVERRIDE_FILE" <<YAML
services:
  postgres:
    ports:
      - "127.0.0.1:${HOST_PORT}:5432"
YAML

SANITIZED_ENV="$ARTIFACT_DIR/compose.env.sanitized"
sed -E 's/(MIEMIE_POSTGRES_PASSWORD=).*/\1<redacted>/; s#(MIEMIE_DATABASE_URL=postgresql\\+psycopg://miemie:)[^@]+#\1<redacted>#' "$ENV_FILE" > "$SANITIZED_ENV"

run_logged "docker-version" docker --version
run_logged "docker-compose-version" docker compose version
run_logged_redacted "compose-config" docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" config
run_logged "postgres-up" docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" up -d postgres

STAGE="postgres-ready"
write_status "$STATE" "$STAGE" ""
for _ in $(seq 1 30); do
  if docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" exec -T postgres pg_isready -U miemie -d miemie >> "$COMMAND_LOG" 2>&1; then
    break
  fi
  sleep 2
done
docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" exec -T postgres pg_isready -U miemie -d miemie >> "$COMMAND_LOG" 2>&1 || mark_failed "$STAGE" "postgres did not become ready"

export MIEMIE_DATABASE_ENABLED=true
export MIEMIE_DATABASE_URL="postgresql+psycopg://miemie:$POSTGRES_PASSWORD@127.0.0.1:${HOST_PORT}/miemie"

run_logged "alembic-upgrade-head" "$PYTHON_BIN" -m alembic -c backend/alembic.ini upgrade head

domains=(
  video_studio_tasks
  studio_tasks
  projects
  media_metadata
  project_entities
  benchmark_records
  user_config
)

for domain in "${domains[@]}"; do
  script_name="scripts/postgres_backfill_${domain}.py"
  run_logged "backfill-$domain" "$PYTHON_BIN" "$script_name" --data-root "$DATA_ROOT" --output "$ARTIFACT_DIR/${domain}_backfill.json"
done

for domain in "${domains[@]}"; do
  script_name="scripts/postgres_reconcile_${domain}.py"
  output_dir="$ARTIFACT_DIR/${domain}_reconcile"
  mkdir -p "$output_dir"
  run_logged "reconcile-$domain" "$PYTHON_BIN" "$script_name" --data-root "$DATA_ROOT" --output-dir "$output_dir"
done

mkdir -p "$BACKUP_DIR"
run_logged "postgres-backup" env PROJECT_NAME="$PROJECT_NAME" ENV_FILE="$ENV_FILE" COMPOSE_FILE_1=docker-compose.yml COMPOSE_FILE_2="$OVERRIDE_FILE" BACKUP_DIR="$BACKUP_DIR" scripts/postgres_backup.sh

LATEST_DUMP="$(find "$BACKUP_DIR" -type f -name '*.dump' -print | sort | tail -n 1)"
if [[ -z "$LATEST_DUMP" ]]; then
  mark_failed "postgres-backup" "backup dump was not created"
fi
run_logged "postgres-restore-rehearsal" env PROJECT_NAME="$PROJECT_NAME" ENV_FILE="$ENV_FILE" COMPOSE_FILE_1=docker-compose.yml COMPOSE_FILE_2="$OVERRIDE_FILE" scripts/postgres_restore_rehearsal.sh "$LATEST_DUMP"

if [[ "$KEEP_REHEARSAL_DB" != "true" ]]; then
  run_logged "compose-down" docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" down -v
fi

STATE="passed"
STAGE="done"
write_status "$STATE" "$STAGE" ""
printf 'passed: PostgreSQL live rehearsal completed. Artifact: %s\n' "$ARTIFACT_DIR"
