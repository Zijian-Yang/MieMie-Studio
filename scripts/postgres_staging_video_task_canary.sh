#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-${MODE:-audit}}"
RUN_ID="${RUN_ID:-postgres-staging-video-task-canary-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r44-staging-video-task-canary}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
PROJECT_NAME="${PROJECT_NAME:-miemie-pre}"
ENV_FILE="${ENV_FILE:-compose.env}"
OVERRIDE_FILE="${OVERRIDE_FILE:-docker-compose.pre.override.yml}"
IMAGE_NAME="${IMAGE_NAME:-miemie-studio:pre-local}"
DOMAIN="video_studio_tasks"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
: > "$COMMAND_LOG"

cleanup_sensitive_tmp() {
  rm -f \
    "$TMP_DIR/register.json" \
    "$TMP_DIR/project.json" \
    "$TMP_DIR/preview.json" \
    "$TMP_DIR/token.txt" \
    "$TMP_DIR/project-id.txt"
}
trap cleanup_sensitive_tmp EXIT

if [[ -x "backend/.venv/bin/python" ]]; then
  JSON_PYTHON="backend/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  JSON_PYTHON="python3"
else
  JSON_PYTHON=""
fi

COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" -p "$PROJECT_NAME")

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
  local reason="${3:-}"
  cat > "$STATUS_FILE" <<JSON
{
  "run_id": "$(json_escape "$RUN_ID")",
  "mode": "$(json_escape "$MODE")",
  "state": "$(json_escape "$state")",
  "stage": "$(json_escape "$stage")",
  "reason": "$(json_escape "$reason")",
  "domain": "$DOMAIN",
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

set_env_value() {
  local key="$1"
  local value="$2"
  local tmp_file
  tmp_file="$(mktemp "$TMP_DIR/env.XXXXXX")"
  awk -v key="$key" -v value="$value" '
    BEGIN { found = 0 }
    $0 ~ "^" key "=" {
      print key "=" value
      found = 1
      next
    }
    { print }
    END {
      if (!found) {
        print key "=" value
      }
    }
  ' "$ENV_FILE" > "$tmp_file"
  cat "$tmp_file" > "$ENV_FILE"
  rm -f "$tmp_file"
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

host_port() {
  local value
  value="$(env_value MIEMIE_HOST_PORT || true)"
  printf '%s' "${value:-18100}"
}

base_url() {
  printf 'http://127.0.0.1:%s' "$(host_port)"
}

repo_head() {
  git rev-parse HEAD 2>/dev/null || printf unknown
}

ensure_preconditions() {
  [[ -f "$ENV_FILE" ]] || blocked "precheck" "missing $ENV_FILE"
  [[ -f docker-compose.yml ]] || blocked "precheck" "missing docker-compose.yml"
  [[ -f "$OVERRIDE_FILE" ]] || blocked "precheck" "missing $OVERRIDE_FILE"
  [[ -n "$JSON_PYTHON" ]] || blocked "precheck" "python3 unavailable"
  command -v docker >/dev/null 2>&1 || blocked "precheck" "docker CLI unavailable"
  docker info >/dev/null 2>"$ARTIFACT_DIR/docker-info.err" || blocked "precheck" "docker daemon unavailable; see docker-info.err"
  "${COMPOSE[@]}" version > "$ARTIFACT_DIR/docker-compose-version.txt" 2>&1 || blocked "precheck" "docker compose unavailable"
}

health_check() {
  local label="$1"
  local expected_version="${2:-}"
  local url
  url="$(base_url)/api/health"
  log_cmd "health-$label" curl -sS -D "$ARTIFACT_DIR/health-$label.headers" -o "$ARTIFACT_DIR/health-$label.json" "$url"
  curl -sS -D "$ARTIFACT_DIR/health-$label.headers" -o "$ARTIFACT_DIR/health-$label.json" --connect-timeout 10 --max-time 20 "$url" \
    >> "$COMMAND_LOG" 2>&1 || return 1
  if [[ -n "$expected_version" ]]; then
    "$JSON_PYTHON" - "$ARTIFACT_DIR/health-$label.json" "$expected_version" <<'PY'
import json
import sys

path, expected = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as handle:
    payload = json.load(handle)
if payload.get("status") != "ok":
    raise SystemExit(f"health status is {payload.get('status')!r}")
actual = payload.get("git_commit")
if actual != expected:
    raise SystemExit(f"deployment version mismatch: {actual} != {expected}")
PY
  fi
}

wait_for_health() {
  local label="$1"
  local expected_version="${2:-}"
  local attempts="${3:-30}"
  for _ in $(seq 1 "$attempts"); do
    if health_check "$label" "$expected_version"; then
      return 0
    fi
    sleep 2
  done
  return 1
}

audit_state() {
  write_status "running" "audit" ""
  date -u +%Y-%m-%dT%H:%M:%SZ > "$ARTIFACT_DIR/audit-time.txt"
  repo_head > "$ARTIFACT_DIR/repo-head.txt"
  redact_env_file "$ARTIFACT_DIR/compose.env.sanitized"
  docker image inspect "$IMAGE_NAME" --format '{{.Id}} {{.Created}}' > "$ARTIFACT_DIR/image-pre-local.txt" 2>"$ARTIFACT_DIR/image-pre-local.err" || true
  "${COMPOSE[@]}" ps > "$ARTIFACT_DIR/compose-ps.txt" 2>&1 || true
  "${COMPOSE[@]}" logs --tail=120 api > "$ARTIFACT_DIR/api.tail.log" 2>&1 || true
  health_check "audit" "" || true
  write_status "passed" "audit" ""
}

backup_env() {
  local backup_name="compose.env.bak-$RUN_ID"
  cp "$ENV_FILE" "$backup_name"
  printf '%s\n' "$backup_name" > "$ARTIFACT_DIR/compose-env-backup.txt"
}

configure_runtime_disabled() {
  local head
  head="$(repo_head)"
  set_env_value MIEMIE_RUNTIME_GIT_COMMIT "$head"
  set_env_value MIEMIE_DATABASE_ENABLED false
  set_env_value MIEMIE_DATABASE_WRITE_MODE file
  set_env_value MIEMIE_DATABASE_READ_MODE file
  set_env_value MIEMIE_DATABASE_DUAL_WRITE_DOMAINS ""
  set_env_value MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS ""
  set_env_value MIEMIE_DATABASE_READ_DOMAINS ""
  set_env_value MIEMIE_DATABASE_JSON_FALLBACK_READ true
  set_env_value MIEMIE_DATABASE_JSON_ARCHIVE_WRITES false
  set_env_value MIEMIE_DATABASE_RECONCILE_STRICT false
  redact_env_file "$ARTIFACT_DIR/compose.env.runtime-disabled.sanitized"
}

roll_runtime() {
  write_status "running" "roll-runtime" ""
  backup_env
  configure_runtime_disabled
  run_logged "docker-compose-build-api" "${COMPOSE[@]}" build api
  run_logged "docker-compose-up-runtime" "${COMPOSE[@]}" up -d api worker worker-video
  wait_for_health "runtime" "$(repo_head)" 45 || fail "runtime-health" "new runtime did not report expected deployment version"
  audit_state
  write_status "passed" "roll-runtime" ""
}

configure_dual_write() {
  set_env_value MIEMIE_DATABASE_ENABLED true
  set_env_value MIEMIE_DATABASE_WRITE_MODE file
  set_env_value MIEMIE_DATABASE_READ_MODE file
  set_env_value MIEMIE_DATABASE_DUAL_WRITE_DOMAINS "$DOMAIN"
  set_env_value MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS ""
  set_env_value MIEMIE_DATABASE_READ_DOMAINS ""
  set_env_value MIEMIE_DATABASE_JSON_FALLBACK_READ true
  set_env_value MIEMIE_DATABASE_JSON_ARCHIVE_WRITES false
  set_env_value MIEMIE_DATABASE_RECONCILE_STRICT false
  redact_env_file "$ARTIFACT_DIR/compose.env.dual-write.sanitized"
}

run_storage_canary() {
  local canary_user="r44_canary_$(date +%Y%m%d%H%M%S)_$RANDOM"
  local canary_project="r44_project_$(date +%Y%m%d%H%M%S)_$RANDOM"
  local canary_task="r44_task_$(date +%Y%m%d%H%M%S)_$RANDOM"
  "${COMPOSE[@]}" exec -T \
    -e CANARY_USER_ID="$canary_user" \
    -e CANARY_PROJECT_ID="$canary_project" \
    -e CANARY_TASK_ID="$canary_task" \
    api /opt/venv/bin/python - <<'PY' > "$ARTIFACT_DIR/storage-canary.json"
import json
import os
from datetime import datetime

from app.db.engine import create_database_engine
from app.models.media import VideoStudioTask
from app.repositories.video_studio_tasks import PostgresVideoStudioTaskRepository
from app.services.storage import get_user_storage, set_current_user

user_id = os.environ["CANARY_USER_ID"]
project_id = os.environ["CANARY_PROJECT_ID"]
task_id = os.environ["CANARY_TASK_ID"]

set_current_user(user_id)
storage = get_user_storage(user_id)
task = VideoStudioTask(
    id=task_id,
    project_id=project_id,
    name="R44 video_studio_tasks dual-write canary",
    task_type="text_to_video",
    task_kind="text_to_video",
    provider="wan",
    model_id="wan2.7-t2v",
    model="wan2.7-t2v",
    prompt="R44 PostgreSQL shadow write canary",
    normalized_params={"resolution": "720P", "duration": 5, "prompt_extend": False, "watermark": False},
    status="canary",
    group_count=1,
)
storage.save_video_studio_task(task)
json_present = storage.get_video_studio_task(task_id) is not None

engine = create_database_engine()
try:
    repo = PostgresVideoStudioTaskRepository(engine, user_id)
    pg_present = repo.get(task_id) is not None
    storage.delete_video_studio_task(task_id)
    pg_after_delete = repo.get(task_id)
finally:
    engine.dispose()

ok = bool(json_present and pg_present and pg_after_delete is None)
print(json.dumps({
    "ok": ok,
    "domain": "video_studio_tasks",
    "json_primary_write_observed": json_present,
    "postgres_shadow_write_observed": pg_present,
    "postgres_shadow_delete_observed": pg_after_delete is None,
    "timestamp": datetime.utcnow().isoformat() + "Z",
}, ensure_ascii=False, indent=2))
if not ok:
    raise SystemExit(1)
PY
}

run_api_preview_smoke() {
  local url token project_id register_body project_body
  url="$(base_url)"
  register_body="$TMP_DIR/register.json"
  project_body="$TMP_DIR/project.json"
  token="$TMP_DIR/token.txt"
  project_id="$TMP_DIR/project-id.txt"
  local username="r44_api_$(date +%Y%m%d%H%M%S)_$RANDOM"
  local password="r44-pass-$(date +%s)-$RANDOM"

  local register_code
  register_code="$(curl -sS -o "$register_body" -w '%{http_code}' --connect-timeout 10 --max-time 20 \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$username\",\"password\":\"$password\",\"display_name\":\"R44 API Canary\"}" \
    "$url/api/auth/register")"
  [[ "$register_code" == "200" ]] || fail "api-register" "register returned HTTP $register_code"
  "$JSON_PYTHON" - "$register_body" "$token" <<'PY'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    handle.write(payload["token"])
PY

  local auth_header
  auth_header="Authorization: Bearer $(cat "$token")"

  local project_code
  project_code="$(curl -sS -o "$project_body" -w '%{http_code}' --connect-timeout 10 --max-time 20 \
    -H 'Content-Type: application/json' -H "$auth_header" \
    -d '{"name":"R44 PostgreSQL canary","description":"temporary canary project"}' \
    "$url/api/projects")"
  [[ "$project_code" == "200" ]] || fail "api-project" "project create returned HTTP $project_code"
  "$JSON_PYTHON" - "$project_body" "$project_id" <<'PY'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    handle.write(payload["id"])
PY

  local pid
  pid="$(cat "$project_id")"
  local preview_code
  preview_code="$(curl -sS -o "$TMP_DIR/preview.json" -w '%{http_code}' --connect-timeout 10 --max-time 20 \
    -H 'Content-Type: application/json' -H "$auth_header" \
    -d "{\"project_id\":\"$pid\",\"task_kind\":\"text_to_video\",\"task_type\":\"text_to_video\",\"provider\":\"wan\",\"model_id\":\"wan2.7-t2v\",\"model\":\"wan2.7-t2v\",\"prompt\":\"R44 preview payload smoke\",\"normalized_params\":{\"resolution\":\"720P\",\"duration\":5,\"prompt_extend\":false,\"watermark\":false},\"group_count\":1}" \
    "$url/api/video-studio/preview-payload")"

  local list_code delete_code logout_code
  list_code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 10 --max-time 20 -H "$auth_header" "$url/api/video-studio?project_id=$pid")"
  delete_code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 10 --max-time 20 -X DELETE -H "$auth_header" "$url/api/projects/$pid")"
  logout_code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 10 --max-time 20 -X POST -H "$auth_header" "$url/api/auth/logout")"

  cat > "$ARTIFACT_DIR/api-preview-smoke.json" <<JSON
{
  "ok": true,
  "register_status": "$register_code",
  "project_create_status": "$project_code",
  "preview_payload_status": "$preview_code",
  "video_studio_list_status": "$list_code",
  "project_delete_status": "$delete_code",
  "logout_status": "$logout_code"
}
JSON
  [[ "$preview_code" =~ ^(2|3) ]] || fail "api-preview" "preview returned HTTP $preview_code"
  [[ "$list_code" == "200" ]] || fail "api-list" "video studio list returned HTTP $list_code"
  [[ "$delete_code" == "200" ]] || fail "api-cleanup" "project delete returned HTTP $delete_code"
}

dual_write_canary() {
  write_status "running" "dual-write-canary" ""
  local head
  head="$(repo_head)"
  health_check "pre-canary" "$head" || blocked "pre-canary" "runtime does not report current repo head; run MODE=roll-runtime first"
  backup_env
  configure_dual_write
  run_logged "docker-compose-up-dual-write" "${COMPOSE[@]}" up -d api worker worker-video
  wait_for_health "dual-write" "$head" 30 || fail "dual-write-health" "dual-write runtime health failed"
  run_storage_canary
  run_api_preview_smoke
  audit_state
  write_status "passed" "dual-write-canary" ""
}

case "$MODE" in
  audit)
    ensure_preconditions
    audit_state
    ;;
  roll-runtime)
    ensure_preconditions
    roll_runtime
    ;;
  dual-write-canary)
    ensure_preconditions
    dual_write_canary
    ;;
  *)
    printf 'usage: MODE=audit|roll-runtime|dual-write-canary %s\n' "$0" >&2
    exit 64
    ;;
esac

printf 'mode=%s state=%s artifact=%s\n' "$MODE" "$("$JSON_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["state"])' "$STATUS_FILE" 2>/dev/null || printf unknown)" "$ARTIFACT_DIR"
