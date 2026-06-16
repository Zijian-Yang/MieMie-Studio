#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-postgres-staging-live-data-gate-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r64-staging-live-data-gate}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
CONFIRM_LIVE_DATA_GATE="${CONFIRM_LIVE_DATA_GATE:-dry-run}"
PROJECT_NAME="${PROJECT_NAME:-miemie-pre}"
ENV_FILE="${ENV_FILE:-compose.env}"
DATA_ROOT="${DATA_ROOT:-backend/data}"
PYTHON_BIN="${PYTHON_BIN:-}"
DOMAINS="${DOMAINS:-video_studio_tasks studio_tasks projects media_metadata project_entities benchmark_records user_config sessions}"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
PLAN_FILE="$ARTIFACT_DIR/live-data-gate-plan.sh"
DOMAINS_FILE="$ARTIFACT_DIR/domains.txt"
MAINTENANCE_ENV_FILE="$TMP_DIR/maintenance.env"
: > "$COMMAND_LOG"

cleanup_sensitive_tmp() {
  rm -f "$MAINTENANCE_ENV_FILE"
}
trap cleanup_sensitive_tmp EXIT

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "backend/.venv/bin/python" ]]; then
    PYTHON_BIN="backend/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN=""
  fi
fi

json_escape() {
  if [[ -n "$PYTHON_BIN" ]]; then
    printf '%s' "$1" | "$PYTHON_BIN" -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
  else
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
  fi
}

write_status() {
  local state="$1"
  local stage="$2"
  local reason="${3:-}"
  cat > "$STATUS_FILE" <<JSON
{
  "run_id": "$(json_escape "$RUN_ID")",
  "state": "$(json_escape "$state")",
  "stage": "$(json_escape "$stage")",
  "reason": "$(json_escape "$reason")",
  "artifact_dir": "$(json_escape "$ARTIFACT_DIR")",
  "tmp_dir": "$(json_escape "$TMP_DIR")",
  "domains": "$(json_escape "$DOMAINS")",
  "confirm": "$(json_escape "$CONFIRM_LIVE_DATA_GATE")",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
}

log_cmd() {
  local label="$1"
  shift
  {
    printf '\n## [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$label"
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  } >> "$COMMAND_LOG"
}

run_logged() {
  local label="$1"
  shift
  log_cmd "$label" "$@"
  "$@" >> "$COMMAND_LOG" 2>&1
}

fail() {
  local stage="$1"
  local reason="$2"
  write_status "failed" "$stage" "$reason"
  printf 'failed: %s\n' "$reason" | tee -a "$COMMAND_LOG" >&2
  exit 1
}

blocked() {
  local stage="$1"
  local reason="$2"
  write_status "blocked" "$stage" "$reason"
  printf 'blocked: %s\n' "$reason" | tee -a "$COMMAND_LOG" >&2
  exit 2
}

env_value() {
  local key="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    return 1
  fi
  grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true
}

expand_database_url() {
  local url="$1"
  local postgres_password postgres_user postgres_db
  postgres_password="$(env_value MIEMIE_POSTGRES_PASSWORD || true)"
  postgres_user="$(env_value MIEMIE_POSTGRES_USER || true)"
  postgres_db="$(env_value MIEMIE_POSTGRES_DB || true)"
  postgres_user="${postgres_user:-miemie}"
  postgres_db="${postgres_db:-miemie}"

  url="${url//\$\{MIEMIE_POSTGRES_PASSWORD\}/$postgres_password}"
  url="${url//\$\{MIEMIE_POSTGRES_PASSWORD:-\}/$postgres_password}"
  url="${url//\$\{MIEMIE_POSTGRES_USER\}/$postgres_user}"
  url="${url//\$\{MIEMIE_POSTGRES_DB\}/$postgres_db}"
  printf '%s' "$url"
}

redact_env_file() {
  local output="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    printf 'missing env file: %s\n' "$ENV_FILE" > "$output"
    return
  fi
  grep -E '^(MIEMIE_RUNTIME_GIT_COMMIT|MIEMIE_HOST|MIEMIE_WORKERS|MIEMIE_TASK|MIEMIE_VIDEO|MIEMIE_DATABASE|MIEMIE_POSTGRES)' "$ENV_FILE" \
    | sed -E \
      -e 's/(MIEMIE_POSTGRES_PASSWORD=).*/\1<redacted>/' \
      -e 's#(MIEMIE_DATABASE_URL=postgresql\+psycopg://miemie:)[^@]+#\1<redacted>#' \
    > "$output"
}

write_domains_file() {
  : > "$DOMAINS_FILE"
  local domain
  for domain in $DOMAINS; do
    printf '%s\n' "$domain" >> "$DOMAINS_FILE"
  done
}

write_maintenance_env() {
  local database_url
  database_url="$(env_value MIEMIE_DATABASE_URL || true)"
  if [[ -z "$database_url" ]]; then
    database_url="$(env_value MIEMIE_POSTGRES_URL || true)"
  fi
  [[ -n "$database_url" ]] || blocked "precheck" "missing MIEMIE_DATABASE_URL in $ENV_FILE"
  database_url="$(expand_database_url "$database_url")"
  [[ "$database_url" != *'${MIEMIE_POSTGRES_PASSWORD}'* ]] || blocked "precheck" "MIEMIE_DATABASE_URL still contains MIEMIE_POSTGRES_PASSWORD placeholder"

  cat > "$MAINTENANCE_ENV_FILE" <<EOF
MIEMIE_DATABASE_URL=$database_url
MIEMIE_DATABASE_ENABLED=true
MIEMIE_DATABASE_WRITE_MODE=file
MIEMIE_DATABASE_READ_MODE=file
MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=
MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=
MIEMIE_DATABASE_READ_DOMAINS=
MIEMIE_DATABASE_JSON_FALLBACK_READ=true
MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false
MIEMIE_DATABASE_RECONCILE_STRICT=true
EOF
  chmod 600 "$MAINTENANCE_ENV_FILE"
  sed -E \
    -e 's#(MIEMIE_DATABASE_URL=postgresql\+psycopg://miemie:)[^@]+#\1<redacted>#' \
    "$MAINTENANCE_ENV_FILE" > "$ARTIFACT_DIR/maintenance.env.sanitized"
}

load_maintenance_env() {
  local key value
  while IFS='=' read -r key value; do
    [[ -n "$key" ]] || continue
    export "$key=$value"
  done < "$MAINTENANCE_ENV_FILE"
}

write_plan() {
  write_domains_file
  cat > "$PLAN_FILE" <<'PLAN'
#!/usr/bin/env bash
set -Eeuo pipefail

# Planned server-side staging data gate. This plan is intentionally redacted.
export MIEMIE_DATABASE_URL='<from compose.env redacted>'
export MIEMIE_DATABASE_ENABLED=true
export MIEMIE_DATABASE_WRITE_MODE=file
export MIEMIE_DATABASE_READ_MODE=file
export MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=
export MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=
export MIEMIE_DATABASE_READ_DOMAINS=
export MIEMIE_DATABASE_JSON_FALLBACK_READ=true
export MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false
export MIEMIE_DATABASE_RECONCILE_STRICT=true

# alembic-upgrade-head: alembic upgrade head
$PYTHON_BIN -m alembic -c backend/alembic.ini upgrade head

# per-domain JSON -> PostgreSQL backfill and reconcile
PLAN
  local domain
  for domain in $DOMAINS; do
    cat >> "$PLAN_FILE" <<PLAN
$PYTHON_BIN scripts/postgres_backfill_${domain}.py --data-root "$DATA_ROOT" --output "\$ARTIFACT_DIR/${domain}_backfill.json"
$PYTHON_BIN scripts/postgres_reconcile_${domain}.py --data-root "$DATA_ROOT" --output-dir "\$ARTIFACT_DIR/${domain}_reconcile"
PLAN
  done
  cat >> "$PLAN_FILE" <<'PLAN'

BACKUP_DIR="$TMP_DIR/postgres-backups" bash scripts/postgres_backup.sh
bash scripts/postgres_restore_rehearsal.sh "$BACKUP_SQL"
PLAN
}

verify_server_context() {
  [[ -f "$ENV_FILE" ]] || blocked "precheck" "missing $ENV_FILE"
  [[ -f docker-compose.yml ]] || blocked "precheck" "missing docker-compose.yml"
  [[ -n "$PYTHON_BIN" ]] || blocked "precheck" "python3 unavailable"
  [[ -d "$DATA_ROOT" ]] || blocked "precheck" "missing data root: $DATA_ROOT"
  [[ -f backend/alembic.ini ]] || blocked "precheck" "missing backend/alembic.ini"
  [[ -f scripts/postgres_backup.sh ]] || blocked "precheck" "missing postgres_backup.sh"
  [[ -f scripts/postgres_restore_rehearsal.sh ]] || blocked "precheck" "missing postgres_restore_rehearsal.sh"
  command -v docker >/dev/null 2>&1 || blocked "precheck" "docker CLI unavailable"
  docker info >/dev/null 2>"$ARTIFACT_DIR/docker-info.err" || blocked "precheck" "docker daemon unavailable; see docker-info.err"

  local domain
  for domain in $DOMAINS; do
    [[ -f "scripts/postgres_backfill_${domain}.py" ]] || blocked "precheck" "missing postgres_backfill_${domain}.py"
    [[ -f "scripts/postgres_reconcile_${domain}.py" ]] || blocked "precheck" "missing postgres_reconcile_${domain}.py"
  done

  redact_env_file "$ARTIFACT_DIR/compose.env.sanitized"
  write_maintenance_env
}

run_alembic_upgrade() {
  write_status "running" "alembic-upgrade-head" ""
  load_maintenance_env
  run_logged "alembic-upgrade-head" "$PYTHON_BIN" -m alembic -c backend/alembic.ini upgrade head
}

run_domain_backfill_and_reconcile() {
  local domain="$1"
  write_status "running" "backfill-$domain" ""
  load_maintenance_env
  run_logged "backfill-$domain" \
    "$PYTHON_BIN" "scripts/postgres_backfill_${domain}.py" \
    --data-root "$DATA_ROOT" \
    --output "$ARTIFACT_DIR/${domain}_backfill.json"

  write_status "running" "reconcile-$domain" ""
  load_maintenance_env
  run_logged "reconcile-$domain" \
    "$PYTHON_BIN" "scripts/postgres_reconcile_${domain}.py" \
    --data-root "$DATA_ROOT" \
    --output-dir "$ARTIFACT_DIR/${domain}_reconcile"
}

run_backup_and_restore_rehearsal() {
  local backup_sql
  write_status "running" "postgres-backup" ""
  mkdir -p "$TMP_DIR/postgres-backups"
  log_cmd "postgres-backup" bash scripts/postgres_backup.sh
  set +e
  backup_sql="$(BACKUP_DIR="$TMP_DIR/postgres-backups" PROJECT_NAME="$PROJECT_NAME" ENV_FILE="$ENV_FILE" bash scripts/postgres_backup.sh 2>>"$COMMAND_LOG")"
  local backup_exit=$?
  set -e
  printf '%s\n' "$backup_sql" > "$ARTIFACT_DIR/postgres-backup-path.txt"
  [[ "$backup_exit" == "0" ]] || fail "postgres-backup" "postgres_backup.sh exited with $backup_exit"
  [[ -s "$backup_sql" ]] || fail "postgres-backup" "backup file is empty: $backup_sql"

  write_status "running" "postgres-restore-rehearsal" ""
  run_logged "postgres-restore-rehearsal" \
    bash scripts/postgres_restore_rehearsal.sh "$backup_sql"
}

main() {
  write_plan
  if [[ "$CONFIRM_LIVE_DATA_GATE" != "run" ]]; then
    write_status "dry_run" "planned" "set CONFIRM_LIVE_DATA_GATE=run to execute"
    printf 'dry-run live data gate plan written to %s\n' "$PLAN_FILE"
    exit 0
  fi

  verify_server_context
  write_status "running" "precheck" ""
  run_alembic_upgrade

  local domain
  for domain in $DOMAINS; do
    run_domain_backfill_and_reconcile "$domain"
  done

  run_backup_and_restore_rehearsal
  write_status "passed" "done" ""
}

main "$@"
