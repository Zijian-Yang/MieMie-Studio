#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-postgres-post-json-exit-validation-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r81-post-json-exit-validation}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
CONFIRM_POST_JSON_EXIT_VALIDATION="${CONFIRM_POST_JSON_EXIT_VALIDATION:-dry-run}"
POST_JSON_EXIT_RUN_LOAD_GATE="${POST_JSON_EXIT_RUN_LOAD_GATE:-true}"
PROJECT_NAME="${PROJECT_NAME:-miemie-pre}"
ENV_FILE="${ENV_FILE:-compose.env}"
OVERRIDE_FILE="${OVERRIDE_FILE:-docker-compose.pre.override.yml}"
DATA_ROOT="${DATA_ROOT:-backend/data}"
DOMAINS="${DOMAINS:-video_studio_tasks studio_tasks projects media_metadata project_entities benchmark_records user_config sessions audio_studio}"
SEQUENCE_ARTIFACT_DIR="${SEQUENCE_ARTIFACT_DIR:-}"
POST_JSON_EXIT_BASE_URL="${POST_JSON_EXIT_BASE_URL:-}"
POST_JSON_EXIT_PUBLIC_URL="${POST_JSON_EXIT_PUBLIC_URL:-https://pre-studio.miemie.co}"
K6_VUS="${K6_VUS:-30}"
K6_DURATION="${K6_DURATION:-90s}"
K6_SLEEP_SECONDS="${K6_SLEEP_SECONDS:-1}"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
PLAN_FILE="$ARTIFACT_DIR/post-json-exit-validation-plan.sh"
DOMAINS_FILE="$ARTIFACT_DIR/domains.txt"
MAINTENANCE_ENV_FILE="$TMP_DIR/maintenance.env"
: > "$COMMAND_LOG"

cleanup_sensitive_tmp() {
  rm -f "$MAINTENANCE_ENV_FILE"
}
trap cleanup_sensitive_tmp EXIT

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
  "confirm": "$(json_escape "$CONFIRM_POST_JSON_EXIT_VALIDATION")",
  "run_load_gate": "$(json_escape "$POST_JSON_EXIT_RUN_LOAD_GATE")",
  "sequence_artifact_dir": "$(json_escape "$SEQUENCE_ARTIFACT_DIR")",
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

host_port() {
  local value
  value="$(env_value MIEMIE_HOST_PORT || true)"
  printf '%s' "${value:-18100}"
}

base_url() {
  if [[ -n "$POST_JSON_EXIT_BASE_URL" ]]; then
    printf '%s' "${POST_JSON_EXIT_BASE_URL%/}"
  else
    printf 'http://127.0.0.1:%s' "$(host_port)"
  fi
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
MIEMIE_DATABASE_WRITE_MODE=postgres
MIEMIE_DATABASE_READ_MODE=postgres
MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=
MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=
MIEMIE_DATABASE_READ_DOMAINS=
MIEMIE_DATABASE_JSON_FALLBACK_READ=false
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
  cat > "$PLAN_FILE" <<PLAN
#!/usr/bin/env bash
set -Eeuo pipefail

# Planned post-JSON-exit validation. The real run is gated by CONFIRM_POST_JSON_EXIT_VALIDATION=run.
python3 scripts/postgres_final_json_exit_audit.py --sequence-artifact-dir "\$SEQUENCE_ARTIFACT_DIR" --env-file "$ENV_FILE" --artifact-dir "\$ARTIFACT_DIR/final-json-exit-audit"
grep -q ready_for_post_json_exit_validation "\$ARTIFACT_DIR/final-json-exit-audit/status.json"

export MIEMIE_DATABASE_ENABLED=true
export MIEMIE_DATABASE_WRITE_MODE=postgres
export MIEMIE_DATABASE_READ_MODE=postgres
export MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=
export MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=
export MIEMIE_DATABASE_READ_DOMAINS=
export MIEMIE_DATABASE_JSON_FALLBACK_READ=false
export MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false
export MIEMIE_DATABASE_RECONCILE_STRICT=true

docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" -p "$PROJECT_NAME" up -d api worker worker-video
curl -sS -D "\$ARTIFACT_DIR/health-local.headers" -o "\$ARTIFACT_DIR/health-local.json" "$(base_url)/api/health"
curl -sS -D "\$ARTIFACT_DIR/health-public.headers" -o "\$ARTIFACT_DIR/health-public.json" "${POST_JSON_EXIT_PUBLIC_URL%/}/api/health"
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" -p "$PROJECT_NAME" ps
docker stats --no-stream
PLAN
  local domain
  for domain in $DOMAINS; do
    cat >> "$PLAN_FILE" <<PLAN
python3 scripts/postgres_reconcile_${domain}.py --data-root "$DATA_ROOT" --output-dir "\$ARTIFACT_DIR/${domain}_reconcile"
PLAN
  done
  cat >> "$PLAN_FILE" <<PLAN
K6_VUS=$K6_VUS K6_DURATION=$K6_DURATION K6_SLEEP_SECONDS=$K6_SLEEP_SECONDS MIEMIE_BASE_URL="$(base_url)" LOADTEST_RUN_ID="\$RUN_ID-post-json-exit-s1" k6 run loadtest/k6/s1-read.js --summary-export "\$ARTIFACT_DIR/k6-s1-read.summary.json"
PLAN
}

verify_preconditions() {
  [[ -f "$ENV_FILE" ]] || blocked "precheck" "missing $ENV_FILE"
  [[ -f docker-compose.yml ]] || blocked "precheck" "missing docker-compose.yml"
  [[ -f "$OVERRIDE_FILE" ]] || blocked "precheck" "missing $OVERRIDE_FILE"
  [[ -d "$DATA_ROOT" ]] || blocked "precheck" "missing data root: $DATA_ROOT"
  [[ -n "$PYTHON_BIN" ]] || blocked "precheck" "python3 unavailable"
  [[ -n "$SEQUENCE_ARTIFACT_DIR" ]] || blocked "precheck" "missing SEQUENCE_ARTIFACT_DIR"
  [[ -d "$SEQUENCE_ARTIFACT_DIR" ]] || blocked "precheck" "missing sequence artifact dir: $SEQUENCE_ARTIFACT_DIR"
  [[ -f scripts/postgres_final_json_exit_audit.py ]] || blocked "precheck" "missing postgres_final_json_exit_audit.py"
  command -v docker >/dev/null 2>&1 || blocked "precheck" "docker CLI unavailable"
  command -v curl >/dev/null 2>&1 || blocked "precheck" "curl unavailable"
  docker info >/dev/null 2>"$ARTIFACT_DIR/docker-info.err" || blocked "precheck" "docker daemon unavailable; see docker-info.err"
  if [[ "$POST_JSON_EXIT_RUN_LOAD_GATE" == "true" ]]; then
    command -v k6 >/dev/null 2>&1 || blocked "precheck" "k6 unavailable"
    [[ -f loadtest/k6/s1-read.js ]] || blocked "precheck" "missing loadtest/k6/s1-read.js"
  fi

  local domain
  for domain in $DOMAINS; do
    [[ -f "scripts/postgres_reconcile_${domain}.py" ]] || blocked "precheck" "missing postgres_reconcile_${domain}.py"
  done

  redact_env_file "$ARTIFACT_DIR/compose.env.sanitized"
  write_maintenance_env
}

run_final_json_exit_audit() {
  write_status "running" "final-json-exit-audit" ""
  run_logged "final-json-exit-audit" \
    "$PYTHON_BIN" scripts/postgres_final_json_exit_audit.py \
    --sequence-artifact-dir "$SEQUENCE_ARTIFACT_DIR" \
    --env-file "$ENV_FILE" \
    --artifact-dir "$ARTIFACT_DIR/final-json-exit-audit" \
    --run-id "$RUN_ID-final-json-exit-audit"
  "$PYTHON_BIN" - "$ARTIFACT_DIR/final-json-exit-audit/status.json" <<'PY' || blocked "final-json-exit-audit" "final JSON exit audit is not ready_for_post_json_exit_validation"
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    status = json.load(handle)
if status.get("state") != "ready_for_post_json_exit_validation":
    raise SystemExit(f"unexpected final JSON exit audit state: {status.get('state')!r}")
PY
}

roll_runtime() {
  write_status "running" "roll-runtime" ""
  run_logged "docker-compose-up-runtime" "${COMPOSE[@]}" up -d api worker worker-video
}

health_check() {
  local label="$1"
  local url="$2"
  log_cmd "health-$label" curl -sS -D "$ARTIFACT_DIR/health-$label.headers" -o "$ARTIFACT_DIR/health-$label.json" "$url"
  curl -sS -D "$ARTIFACT_DIR/health-$label.headers" -o "$ARTIFACT_DIR/health-$label.json" --connect-timeout 10 --max-time 20 "$url" \
    >> "$COMMAND_LOG" 2>&1 || failed "health-$label" "health check failed for $url"
}

run_health_gates() {
  write_status "running" "health" ""
  health_check "local" "$(base_url)/api/health"
  if [[ -n "$POST_JSON_EXIT_PUBLIC_URL" ]]; then
    health_check "public" "${POST_JSON_EXIT_PUBLIC_URL%/}/api/health"
  fi
}

run_compose_observability() {
  write_status "running" "compose-observability" ""
  run_logged "docker-compose-ps" "${COMPOSE[@]}" ps
  run_logged "docker-stats" docker stats --no-stream
}

run_domain_reconcile() {
  local domain="$1"
  write_status "running" "reconcile-$domain" ""
  load_maintenance_env
  run_logged "reconcile-$domain" \
    "$PYTHON_BIN" "scripts/postgres_reconcile_${domain}.py" \
    --data-root "$DATA_ROOT" \
    --output-dir "$ARTIFACT_DIR/${domain}_reconcile"
}

run_load_gate() {
  if [[ "$POST_JSON_EXIT_RUN_LOAD_GATE" != "true" ]]; then
    write_status "running" "load-gate-skipped" "POST_JSON_EXIT_RUN_LOAD_GATE is not true"
    return 0
  fi
  write_status "running" "load-gate" ""
  log_cmd "k6-s1-read" k6 run loadtest/k6/s1-read.js
  K6_VUS="$K6_VUS" \
    K6_DURATION="$K6_DURATION" \
    K6_SLEEP_SECONDS="$K6_SLEEP_SECONDS" \
    MIEMIE_BASE_URL="$(base_url)" \
    LOADTEST_RUN_ID="$RUN_ID-post-json-exit-s1" \
    SCENARIO_NAME="post-json-exit-s1-read" \
    k6 run --summary-export "$ARTIFACT_DIR/k6-s1-read.summary.json" loadtest/k6/s1-read.js \
    >> "$COMMAND_LOG" 2>&1 || failed "load-gate" "k6 S1 read gate failed"
}

main() {
  write_plan
  if [[ "$CONFIRM_POST_JSON_EXIT_VALIDATION" != "run" ]]; then
    write_status "dry_run" "planned" "set CONFIRM_POST_JSON_EXIT_VALIDATION=run to execute"
    printf 'dry-run post JSON exit validation plan written to %s\n' "$PLAN_FILE"
    return 0
  fi

  write_status "running" "precheck" ""
  verify_preconditions
  run_final_json_exit_audit
  roll_runtime
  run_health_gates

  local domain
  for domain in $DOMAINS; do
    run_domain_reconcile "$domain"
  done

  run_compose_observability
  run_load_gate
  write_status "passed" "done" ""
}

main "$@"
