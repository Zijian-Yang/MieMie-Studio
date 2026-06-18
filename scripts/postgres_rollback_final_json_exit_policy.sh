#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-postgres-rollback-final-json-exit-policy-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r83-rollback-final-json-exit-policy}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY="${CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY:-dry-run}"
ENV_FILE="${ENV_FILE:-compose.env}"
ROLLBACK_ENV_BACKUP_FILE="${ROLLBACK_ENV_BACKUP_FILE:-}"
PROJECT_NAME="${PROJECT_NAME:-miemie-pre}"
OVERRIDE_FILE="${OVERRIDE_FILE:-docker-compose.pre.override.yml}"
POST_ROLLBACK_BASE_URL="${POST_ROLLBACK_BASE_URL:-}"
POST_ROLLBACK_PUBLIC_URL="${POST_ROLLBACK_PUBLIC_URL:-https://pre-studio.miemie.co}"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
PLAN_FILE="$ARTIFACT_DIR/rollback-final-json-exit-policy-plan.sh"
: > "$COMMAND_LOG"

if [[ -x "backend/.venv/bin/python" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-backend/.venv/bin/python}"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON_BIN:-python3}"
else
  PYTHON_BIN="${PYTHON_BIN:-}"
fi

COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" -p "$PROJECT_NAME")

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
  "confirm": "$(json_escape "$CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY")",
  "env_file": "$(json_escape "$ENV_FILE")",
  "rollback_env_backup_file": "$(json_escape "$ROLLBACK_ENV_BACKUP_FILE")",
  "artifact_dir": "$(json_escape "$ARTIFACT_DIR")",
  "tmp_dir": "$(json_escape "$TMP_DIR")",
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

blocked() {
  local stage="$1"
  local reason="$2"
  write_status "blocked" "$stage" "$reason"
  printf 'blocked: %s\n' "$reason" | tee -a "$COMMAND_LOG" >&2
  exit 2
}

failed() {
  local stage="$1"
  local reason="$2"
  write_status "failed" "$stage" "$reason"
  printf 'failed: %s\n' "$reason" | tee -a "$COMMAND_LOG" >&2
  exit 1
}

redact_env_file() {
  local input="$1"
  local output="$2"
  if [[ ! -f "$input" ]]; then
    printf 'missing env file: %s\n' "$input" > "$output"
    return
  fi
  grep -E '^(MIEMIE_RUNTIME_GIT_COMMIT|MIEMIE_HOST|MIEMIE_WORKERS|MIEMIE_TASK|MIEMIE_VIDEO|MIEMIE_DATABASE|MIEMIE_POSTGRES)' "$input" \
    | sed -E \
      -e 's/(MIEMIE_POSTGRES_PASSWORD=).*/\1<redacted>/' \
      -e 's#(MIEMIE_DATABASE_URL=postgresql\+psycopg://miemie:)[^@]+#\1<redacted>#' \
    > "$output"
}

env_value() {
  local key="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    return 1
  fi
  grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true
}

host_port() {
  local value
  value="$(env_value MIEMIE_HOST_PORT || true)"
  printf '%s' "${value:-18100}"
}

base_url() {
  if [[ -n "$POST_ROLLBACK_BASE_URL" ]]; then
    printf '%s' "${POST_ROLLBACK_BASE_URL%/}"
  else
    printf 'http://127.0.0.1:%s' "$(host_port)"
  fi
}

write_plan() {
  local pre_backup_file
  pre_backup_file="$ARTIFACT_DIR/compose.env.before-final-policy-rollback.$RUN_ID.bak"
  cat > "$PLAN_FILE" <<PLAN
#!/usr/bin/env bash
set -Eeuo pipefail

# Planned final JSON exit policy rollback. The real run is gated by CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY=run.
PRE_ROLLBACK_BACKUP_FILE="$pre_backup_file"
cp "\$ENV_FILE" "\$PRE_ROLLBACK_BACKUP_FILE"
cp "\$ROLLBACK_ENV_BACKUP_FILE" "\$ENV_FILE"
# writes compose.env.rollback-source.sanitized
# writes compose.env.before-rollback.sanitized
# writes compose.env.after-rollback.sanitized
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" -p "$PROJECT_NAME" up -d api worker worker-video
wait_for_health local "$(base_url)/api/health"
wait_for_health public "${POST_ROLLBACK_PUBLIC_URL%/}/api/health"
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" -p "$PROJECT_NAME" ps
PLAN
}

verify_preconditions() {
  [[ -n "$PYTHON_BIN" ]] || blocked "precheck" "python unavailable"
  [[ -f "$ENV_FILE" ]] || blocked "precheck" "missing $ENV_FILE"
  [[ -n "$ROLLBACK_ENV_BACKUP_FILE" ]] || blocked "precheck" "missing ROLLBACK_ENV_BACKUP_FILE"
  [[ -f "$ROLLBACK_ENV_BACKUP_FILE" ]] || blocked "precheck" "missing rollback backup file: $ROLLBACK_ENV_BACKUP_FILE"
  [[ -f docker-compose.yml ]] || blocked "precheck" "missing docker-compose.yml"
  [[ -f "$OVERRIDE_FILE" ]] || blocked "precheck" "missing $OVERRIDE_FILE"
  command -v docker >/dev/null 2>&1 || blocked "precheck" "docker CLI unavailable"
  command -v curl >/dev/null 2>&1 || blocked "precheck" "curl unavailable"
  docker info >/dev/null 2>"$ARTIFACT_DIR/docker-info.err" || blocked "precheck" "docker daemon unavailable; see docker-info.err"
}

health_check() {
  local label="$1"
  local url="$2"
  log_cmd "health-$label" curl -sS -D "$ARTIFACT_DIR/health-$label.headers" -o "$ARTIFACT_DIR/health-$label.json" "$url"
  curl -sS -D "$ARTIFACT_DIR/health-$label.headers" -o "$ARTIFACT_DIR/health-$label.json" --connect-timeout 10 --max-time 20 "$url" \
    >> "$COMMAND_LOG" 2>&1
}

wait_for_health() {
  local label="$1"
  local url="$2"
  local attempts="${3:-45}"
  local attempt
  for attempt in $(seq 1 "$attempts"); do
    if health_check "$label" "$url"; then
      return 0
    fi
    printf 'health check did not pass for %s on attempt %s/%s\n' "$url" "$attempt" "$attempts" >> "$COMMAND_LOG"
    sleep 2
  done
  failed "health-$label" "health check did not pass for $url"
}

main() {
  write_plan
  if [[ "$CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY" != "run" ]]; then
    write_status "dry_run" "planned" "set CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY=run to execute"
    printf 'dry-run final JSON exit rollback plan written to %s\n' "$PLAN_FILE"
    return 0
  fi

  verify_preconditions
  local pre_backup_file="$ARTIFACT_DIR/compose.env.before-final-policy-rollback.$RUN_ID.bak"
  cp "$ENV_FILE" "$pre_backup_file"
  chmod 600 "$pre_backup_file"
  redact_env_file "$ROLLBACK_ENV_BACKUP_FILE" "$ARTIFACT_DIR/compose.env.rollback-source.sanitized"
  redact_env_file "$pre_backup_file" "$ARTIFACT_DIR/compose.env.before-rollback.sanitized"

  write_status "running" "restore-env" ""
  cp "$ROLLBACK_ENV_BACKUP_FILE" "$ENV_FILE"
  redact_env_file "$ENV_FILE" "$ARTIFACT_DIR/compose.env.after-rollback.sanitized"

  write_status "running" "roll-runtime" ""
  run_logged "docker-compose-up-runtime" "${COMPOSE[@]}" up -d api worker worker-video

  write_status "running" "health" ""
  wait_for_health "local" "$(base_url)/api/health"
  if [[ -n "$POST_ROLLBACK_PUBLIC_URL" ]]; then
    wait_for_health "public" "${POST_ROLLBACK_PUBLIC_URL%/}/api/health"
  fi
  run_logged "docker-compose-ps" "${COMPOSE[@]}" ps
  write_status "passed" "done" ""
}

main "$@"
