#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-postgres-operational-readiness-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r115-postgres-operational-readiness}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
CONFIRM_POSTGRES_OPERATIONAL_READINESS="${CONFIRM_POSTGRES_OPERATIONAL_READINESS:-dry-run}"
POSTGRES_OPS_BACKUP_RESTORE="${POSTGRES_OPS_BACKUP_RESTORE:-skip}"
PROJECT_NAME="${PROJECT_NAME:-miemie-pre}"
ENV_FILE="${ENV_FILE:-compose.env}"
COMPOSE_FILE_1="${COMPOSE_FILE_1:-docker-compose.yml}"
COMPOSE_FILE_2="${COMPOSE_FILE_2:-docker-compose.pre.override.yml}"
DATA_ROOT="${DATA_ROOT:-backend/data}"
BACKUP_DIR="${BACKUP_DIR:-backend/backups/postgres}"
BACKUP_MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-26}"
LOCAL_HEALTH_URL="${LOCAL_HEALTH_URL:-http://127.0.0.1:18100/api/health}"
PUBLIC_HEALTH_URL="${PUBLIC_HEALTH_URL:-https://pre-studio.miemie.co/api/health}"
ALLOWED_REMAINING_JSON="${ALLOWED_REMAINING_JSON:-backend/data/config.example.json}"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

if [[ -f scripts/postgres_ops_alert.sh ]]; then
  # shellcheck source=scripts/postgres_ops_alert.sh
  source scripts/postgres_ops_alert.sh
fi

STATUS_FILE="$ARTIFACT_DIR/status.json"
RESULTS_FILE="$ARTIFACT_DIR/results.tsv"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
PLAN_FILE="$ARTIFACT_DIR/postgres-operational-readiness-plan.sh"
: > "$COMMAND_LOG"
printf 'check\tstate\tdetail\n' > "$RESULTS_FILE"

PASSED=0
WARNED=0
BLOCKED=0
FAILED=0

if [[ -x "backend/.venv/bin/python" ]]; then
  JSON_PYTHON="backend/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  JSON_PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  JSON_PYTHON="python"
else
  JSON_PYTHON=""
fi

json_escape() {
  if [[ -n "$JSON_PYTHON" ]]; then
    printf '%s' "$1" | "$JSON_PYTHON" -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
  else
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
  fi
}

record_result() {
  local check="$1"
  local state="$2"
  local detail="${3:-}"
  printf '%s\t%s\t%s\n' "$check" "$state" "$detail" >> "$RESULTS_FILE"
  case "$state" in
    passed) PASSED=$((PASSED + 1)) ;;
    warn) WARNED=$((WARNED + 1)) ;;
    blocked) BLOCKED=$((BLOCKED + 1)) ;;
    failed) FAILED=$((FAILED + 1)) ;;
  esac
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
  "confirm": "$(json_escape "$CONFIRM_POSTGRES_OPERATIONAL_READINESS")",
  "backup_restore": "$(json_escape "$POSTGRES_OPS_BACKUP_RESTORE")",
  "backup_max_age_hours": "$(json_escape "$BACKUP_MAX_AGE_HOURS")",
  "artifact_dir": "$(json_escape "$ARTIFACT_DIR")",
  "tmp_dir": "$(json_escape "$TMP_DIR")",
  "counts": {
    "passed": $PASSED,
    "warn": $WARNED,
    "blocked": $BLOCKED,
    "failed": $FAILED
  },
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

send_ops_alert() {
  if type postgres_ops_send_alert >/dev/null 2>&1; then
    postgres_ops_send_alert "$@"
  fi
}

env_value() {
  local key="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    return 1
  fi
  grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true
}

redact_env_file() {
  local output="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    printf 'missing env file: %s\n' "$ENV_FILE" > "$output"
    return
  fi
  grep -E '^(MIEMIE_HOST|MIEMIE_WORKERS|MIEMIE_RUNTIME|MIEMIE_REDIS|MIEMIE_TASK|MIEMIE_CELERY|MIEMIE_VIDEO|MIEMIE_DATABASE|MIEMIE_POSTGRES|TZ=)' "$ENV_FILE" \
    | sed -E \
      -e 's/(MIEMIE_POSTGRES_PASSWORD=).*/\1<redacted>/' \
      -e 's#(MIEMIE_DATABASE_URL=postgresql\+psycopg://miemie:)[^@]+#\1<redacted>#' \
    > "$output" || true
}

write_plan() {
  cat > "$PLAN_FILE" <<PLAN
#!/usr/bin/env bash
set -Eeuo pipefail

# PostgreSQL-only operational readiness gate.
# Default mode is dry-run. Execute checks with:
# CONFIRM_POSTGRES_OPERATIONAL_READINESS=run bash scripts/postgres_operational_readiness.sh
#
# To create a fresh dump and restore it into an isolated rehearsal database:
# CONFIRM_POSTGRES_OPERATIONAL_READINESS=run POSTGRES_OPS_BACKUP_RESTORE=run bash scripts/postgres_operational_readiness.sh

# Checks:
# - compose.env keeps final PostgreSQL-only policy:
#   MIEMIE_DATABASE_ENABLED=true
#   MIEMIE_DATABASE_WRITE_MODE=postgres
#   MIEMIE_DATABASE_READ_MODE=postgres
#   MIEMIE_DATABASE_JSON_FALLBACK_READ=false
#   MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false
#   MIEMIE_DATABASE_RECONCILE_STRICT=true
# - local and public /api/health report status=ok and database.ok=true
# - Compose containers are visible and Docker stats can be collected
# - remaining JSON outside quarantine exactly matches: $ALLOWED_REMAINING_JSON
# - a fresh PostgreSQL backup exists, or POSTGRES_OPS_BACKUP_RESTORE=run creates and restores one
PLAN
}

require_command() {
  local check="$1"
  local cmd="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    record_result "$check" "passed" "$(command -v "$cmd")"
  else
    record_result "$check" "blocked" "$cmd missing"
  fi
}

check_files_and_tools() {
  [[ -n "$JSON_PYTHON" ]] && record_result "python" "passed" "$JSON_PYTHON" || record_result "python" "blocked" "python3 missing"
  [[ -f "$ENV_FILE" ]] && record_result "env_file" "passed" "$ENV_FILE" || record_result "env_file" "blocked" "missing $ENV_FILE"
  [[ -f "$COMPOSE_FILE_1" ]] && record_result "compose_file" "passed" "$COMPOSE_FILE_1" || record_result "compose_file" "blocked" "missing $COMPOSE_FILE_1"
  [[ -d "$DATA_ROOT" ]] && record_result "data_root" "passed" "$DATA_ROOT" || record_result "data_root" "blocked" "missing $DATA_ROOT"
  [[ -f scripts/postgres_backup.sh ]] && record_result "postgres_backup_script" "passed" "present" || record_result "postgres_backup_script" "blocked" "missing"
  [[ -f scripts/postgres_restore_rehearsal.sh ]] && record_result "postgres_restore_rehearsal_script" "passed" "present" || record_result "postgres_restore_rehearsal_script" "blocked" "missing"
  require_command "curl" "curl"
  require_command "docker" "docker"
}

check_env_equals() {
  local key="$1"
  local expected="$2"
  local value
  value="$(env_value "$key")"
  if [[ "$value" == "$expected" ]]; then
    record_result "env:$key" "passed" "$expected"
  else
    record_result "env:$key" "blocked" "expected $expected, got ${value:-<empty>}"
  fi
}

check_final_policy() {
  redact_env_file "$ARTIFACT_DIR/compose.env.sanitized"
  check_env_equals MIEMIE_DATABASE_ENABLED true
  check_env_equals MIEMIE_DATABASE_WRITE_MODE postgres
  check_env_equals MIEMIE_DATABASE_READ_MODE postgres
  check_env_equals MIEMIE_DATABASE_JSON_FALLBACK_READ false
  check_env_equals MIEMIE_DATABASE_JSON_ARCHIVE_WRITES false
  check_env_equals MIEMIE_DATABASE_RECONCILE_STRICT true

  local dual read_domains primary
  dual="$(env_value MIEMIE_DATABASE_DUAL_WRITE_DOMAINS)"
  read_domains="$(env_value MIEMIE_DATABASE_READ_DOMAINS)"
  primary="$(env_value MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS)"
  [[ -z "$dual" ]] && record_result "env:MIEMIE_DATABASE_DUAL_WRITE_DOMAINS" "passed" "empty" || record_result "env:MIEMIE_DATABASE_DUAL_WRITE_DOMAINS" "blocked" "expected empty, got $dual"
  [[ -z "$read_domains" ]] && record_result "env:MIEMIE_DATABASE_READ_DOMAINS" "passed" "empty" || record_result "env:MIEMIE_DATABASE_READ_DOMAINS" "blocked" "expected empty, got $read_domains"
  [[ -z "$primary" ]] && record_result "env:MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS" "passed" "empty" || record_result "env:MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS" "blocked" "expected empty, got $primary"
}

check_health_endpoint() {
  local label="$1"
  local url="$2"
  local headers="$ARTIFACT_DIR/health-${label}.headers.txt"
  local body="$ARTIFACT_DIR/health-${label}.json"

  log_cmd "health-$label" curl -fsS -D "$headers" -o "$body" --connect-timeout 10 --max-time 20 "$url"
  if curl -fsS -D "$headers" -o "$body" --connect-timeout 10 --max-time 20 "$url" >> "$COMMAND_LOG" 2>&1; then
    if "$JSON_PYTHON" - "$body" "$label" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
label = sys.argv[2]
payload = json.loads(path.read_text(encoding="utf-8"))
ok = (
    payload.get("status") == "ok"
    and payload.get("database", {}).get("ok") is True
    and payload.get("redis", {}).get("ok") is True
)
if not ok:
    raise SystemExit(f"health {label} not ok: {payload}")
PY
    then
      record_result "health:$label" "passed" "$url"
    else
      record_result "health:$label" "blocked" "health payload not ok: $url"
    fi
  else
    record_result "health:$label" "blocked" "curl failed: $url"
  fi
}

check_compose_state() {
  local compose_cmd=(docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE_1")
  if [[ -f "$COMPOSE_FILE_2" ]]; then
    compose_cmd+=(-f "$COMPOSE_FILE_2")
  fi

  log_cmd "compose-ps" "${compose_cmd[@]}" ps
  if "${compose_cmd[@]}" ps > "$ARTIFACT_DIR/compose-ps.txt" 2>>"$COMMAND_LOG"; then
    record_result "compose_ps" "passed" "compose-ps.txt"
  else
    record_result "compose_ps" "blocked" "docker compose ps failed"
  fi

  log_cmd "docker-stats" docker stats --no-stream
  if docker stats --no-stream > "$ARTIFACT_DIR/docker-stats.txt" 2>>"$COMMAND_LOG"; then
    record_result "docker_stats" "passed" "docker-stats.txt"
  else
    record_result "docker_stats" "warn" "docker stats failed"
  fi
}

check_remaining_json() {
  local output="$ARTIFACT_DIR/remaining-json-outside-quarantine.txt"
  find "$DATA_ROOT" -path "$DATA_ROOT/_postgres_final_json_archive" -prune -o -name "*.json" -print | sort > "$output"
  if "$JSON_PYTHON" - "$output" "$ALLOWED_REMAINING_JSON" <<'PY'
import sys
from pathlib import Path

actual = [line for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line]
expected = [item for item in sys.argv[2].split() if item]
if actual != expected:
    raise SystemExit(f"remaining JSON mismatch: actual={actual!r} expected={expected!r}")
PY
  then
    record_result "remaining_json" "passed" "$ALLOWED_REMAINING_JSON"
  else
    record_result "remaining_json" "blocked" "unexpected JSON outside quarantine"
  fi
}

latest_backup_json() {
  "$JSON_PYTHON" - "$BACKUP_DIR" "$BACKUP_MAX_AGE_HOURS" <<'PY'
import json
import sys
import time
from pathlib import Path

backup_dir = Path(sys.argv[1])
max_age_hours = float(sys.argv[2])
files = sorted(backup_dir.glob("miemie-postgres-*.sql"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True) if backup_dir.exists() else []
latest = files[0] if files else None
payload = {
    "backup_dir": str(backup_dir),
    "exists": latest is not None,
    "path": str(latest) if latest else "",
    "size_bytes": latest.stat().st_size if latest else 0,
    "age_hours": ((time.time() - latest.stat().st_mtime) / 3600) if latest else None,
    "max_age_hours": max_age_hours,
    "fresh": bool(latest and latest.stat().st_size > 0 and ((time.time() - latest.stat().st_mtime) / 3600) <= max_age_hours),
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY
}

check_backup_freshness_or_run_rehearsal() {
  mkdir -p "$BACKUP_DIR"
  latest_backup_json > "$ARTIFACT_DIR/latest-backup.json"
  if [[ "$POSTGRES_OPS_BACKUP_RESTORE" != "run" ]] && "$JSON_PYTHON" - "$ARTIFACT_DIR/latest-backup.json" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
raise SystemExit(0 if payload.get("fresh") else 1)
PY
  then
    local latest
    latest="$("$JSON_PYTHON" - "$ARTIFACT_DIR/latest-backup.json" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("path", ""))
PY
)"
    record_result "postgres_backup_freshness" "passed" "$latest"
    return
  fi

  if [[ "$POSTGRES_OPS_BACKUP_RESTORE" != "run" ]]; then
    record_result "postgres_backup_freshness" "blocked" "no fresh backup; set POSTGRES_OPS_BACKUP_RESTORE=run to create and restore one"
    return
  fi

  local backup_sql
  log_cmd "postgres-backup" bash scripts/postgres_backup.sh
  set +e
  backup_sql="$(BACKUP_DIR="$BACKUP_DIR" PROJECT_NAME="$PROJECT_NAME" ENV_FILE="$ENV_FILE" COMPOSE_FILE_1="$COMPOSE_FILE_1" COMPOSE_FILE_2="$COMPOSE_FILE_2" bash scripts/postgres_backup.sh 2>>"$COMMAND_LOG")"
  local backup_exit=$?
  set -e
  printf '%s\n' "$backup_sql" > "$ARTIFACT_DIR/postgres-backup-path.txt"
  if [[ "$backup_exit" != "0" || ! -s "$backup_sql" ]]; then
    record_result "postgres_backup" "blocked" "backup failed or empty: $backup_sql"
    return
  fi
  record_result "postgres_backup" "passed" "$backup_sql"

  log_cmd "postgres-restore-rehearsal" bash scripts/postgres_restore_rehearsal.sh "$backup_sql"
  if bash scripts/postgres_restore_rehearsal.sh "$backup_sql" >> "$COMMAND_LOG" 2>&1; then
    record_result "postgres_restore_rehearsal" "passed" "restore rehearsal ok"
  else
    record_result "postgres_restore_rehearsal" "blocked" "restore rehearsal failed"
    return
  fi

  latest_backup_json > "$ARTIFACT_DIR/latest-backup.json"
}

main() {
  write_plan
  if [[ "$CONFIRM_POSTGRES_OPERATIONAL_READINESS" != "run" ]]; then
    write_status "dry_run" "planned" "set CONFIRM_POSTGRES_OPERATIONAL_READINESS=run to execute"
    printf 'dry-run operational readiness plan written to %s\n' "$PLAN_FILE"
    exit 0
  fi

  date -u +%Y-%m-%dT%H:%M:%SZ > "$ARTIFACT_DIR/time.txt"
  git rev-parse HEAD > "$ARTIFACT_DIR/git-head.txt" 2>/dev/null || true
  git status --short > "$ARTIFACT_DIR/git-status-short.txt" 2>/dev/null || true

  check_files_and_tools
  check_final_policy
  if [[ "$BLOCKED" -eq 0 && "$FAILED" -eq 0 ]]; then
    check_health_endpoint "local" "$LOCAL_HEALTH_URL"
    check_health_endpoint "public" "$PUBLIC_HEALTH_URL"
    check_compose_state
    check_remaining_json
    check_backup_freshness_or_run_rehearsal
  fi

  if [[ "$BLOCKED" -gt 0 || "$FAILED" -gt 0 ]]; then
    write_status "blocked" "done" "$BLOCKED blocked, $FAILED failed, $WARNED warnings"
    send_ops_alert "critical" "postgres_operational_readiness" "blocked" "$BLOCKED blocked, $FAILED failed, $WARNED warnings" "$ARTIFACT_DIR"
    exit 2
  fi
  if [[ "$WARNED" -gt 0 ]]; then
    write_status "passed_with_warnings" "done" "$WARNED warnings"
    if [[ "${MIEMIE_OPS_ALERT_ON_WARNING:-false}" == "true" ]]; then
      send_ops_alert "warning" "postgres_operational_readiness" "passed_with_warnings" "$WARNED warnings" "$ARTIFACT_DIR"
    fi
    exit 0
  fi
  write_status "passed" "done" ""
}

main "$@"
