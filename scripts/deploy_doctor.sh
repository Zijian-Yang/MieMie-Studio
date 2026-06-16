#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-deploy-doctor-$(date +%Y%m%d%H%M%S)}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$TMP_DIR/artifacts}"
DOCTOR_PROFILE="${DOCTOR_PROFILE:-all}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-compose.env}"
MIEMIE_DEPLOY_DOCTOR_DRY_RUN="${MIEMIE_DEPLOY_DOCTOR_DRY_RUN:-false}"
MIEMIE_DEPLOY_DOCTOR_RUN_DOCKER_INFO="${MIEMIE_DEPLOY_DOCTOR_RUN_DOCKER_INFO:-false}"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
RESULTS_FILE="$ARTIFACT_DIR/results.tsv"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
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
  "profile": "$(json_escape "$DOCTOR_PROFILE")",
  "compose_env_file": "$(json_escape "$COMPOSE_ENV_FILE")",
  "counts": {
    "passed": $PASSED,
    "warn": $WARNED,
    "blocked": $BLOCKED,
    "failed": $FAILED
  },
  "artifact_dir": "$(json_escape "$ARTIFACT_DIR")",
  "tmp_dir": "$(json_escape "$TMP_DIR")",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
}

profile_requires_compose() {
  [[ "$DOCTOR_PROFILE" == "compose" ]]
}

profile_allows_compose() {
  [[ "$DOCTOR_PROFILE" == "all" || "$DOCTOR_PROFILE" == "compose" ]]
}

warn_or_block_for_compose() {
  local check="$1"
  local detail="$2"
  if profile_requires_compose; then
    record_result "$check" "blocked" "$detail"
  else
    record_result "$check" "warn" "$detail"
  fi
}

command_version() {
  local cmd="$1"
  local version_args="${2:---version}"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    return 1
  fi
  "$cmd" $version_args 2>&1 | head -n 1
}

version_at_least() {
  local current="$1"
  local minimum="$2"
  [[ -n "$JSON_PYTHON" ]] || return 1
  "$JSON_PYTHON" - "$current" "$minimum" <<'PY'
import re
import sys

current, minimum = sys.argv[1], sys.argv[2]

def parse(value: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", value)
    if not match:
        return (0, 0, 0)
    return tuple(int(part or 0) for part in match.groups())

raise SystemExit(0 if parse(current) >= parse(minimum) else 1)
PY
}

check_command_exists() {
  local check="$1"
  local cmd="$2"
  local required="${3:-true}"
  if command -v "$cmd" >/dev/null 2>&1; then
    record_result "$check" "passed" "$(command -v "$cmd")"
  elif [[ "$required" == "true" ]]; then
    record_result "$check" "blocked" "$cmd missing"
  else
    record_result "$check" "warn" "$cmd missing"
  fi
}

check_python() {
  local python_cmd=""
  if command -v python3 >/dev/null 2>&1; then
    python_cmd="python3"
  elif command -v python >/dev/null 2>&1; then
    python_cmd="python"
  fi
  if [[ -z "$python_cmd" ]]; then
    record_result "python" "blocked" "python3 missing"
    return
  fi
  local version
  version="$("$python_cmd" --version 2>&1)"
  if version_at_least "$version" "3.10.0"; then
    record_result "python" "passed" "$version"
  else
    record_result "python" "blocked" "$version < 3.10"
  fi
}

check_node() {
  if ! command -v node >/dev/null 2>&1; then
    record_result "node" "blocked" "node missing"
    return
  fi
  local version
  version="$(node --version 2>&1)"
  if version_at_least "$version" "18.0.0"; then
    record_result "node" "passed" "$version"
  else
    record_result "node" "blocked" "$version < 18"
  fi
}

check_required_files() {
  local missing=0
  local path
  for path in \
    "run.sh" \
    "requirements.txt" \
    "backend/app/main.py" \
    "frontend/package.json" \
    "Dockerfile" \
    "docker-compose.yml" \
    "compose.env.example"; do
    if [[ -e "$path" ]]; then
      record_result "file:$path" "passed" "present"
    else
      record_result "file:$path" "blocked" "missing"
      missing=$((missing + 1))
    fi
  done
}

env_value() {
  local key="$1"
  local file="$2"
  grep -E "^${key}=" "$file" | tail -n 1 | cut -d= -f2- || true
}

redact_compose_env() {
  local output="$1"
  [[ -f "$COMPOSE_ENV_FILE" ]] || return 0
  grep -E '^(MIEMIE_HOST|MIEMIE_WORKERS|MIEMIE_RUNTIME|MIEMIE_REDIS|MIEMIE_TASK|MIEMIE_CELERY|MIEMIE_VIDEO|MIEMIE_DATABASE|MIEMIE_POSTGRES|TZ=)' "$COMPOSE_ENV_FILE" \
    | sed -E \
      -e 's/(MIEMIE_POSTGRES_PASSWORD=).*/\1<redacted>/' \
      -e 's#(MIEMIE_DATABASE_URL=postgresql\+psycopg://miemie:)[^@]+#\1<redacted>#' \
    > "$output" || true
}

check_compose_env() {
  if [[ ! -f "$COMPOSE_ENV_FILE" ]]; then
    warn_or_block_for_compose "compose_env" "missing $COMPOSE_ENV_FILE; copy compose.env.example first"
    return
  fi

  record_result "compose_env" "passed" "$COMPOSE_ENV_FILE present"
  redact_compose_env "$ARTIFACT_DIR/compose.env.sanitized"

  local postgres_password runtime_commit host_bind database_enabled database_url
  postgres_password="$(env_value MIEMIE_POSTGRES_PASSWORD "$COMPOSE_ENV_FILE")"
  runtime_commit="$(env_value MIEMIE_RUNTIME_GIT_COMMIT "$COMPOSE_ENV_FILE")"
  host_bind="$(env_value MIEMIE_HOST_BIND "$COMPOSE_ENV_FILE")"
  database_enabled="$(env_value MIEMIE_DATABASE_ENABLED "$COMPOSE_ENV_FILE")"
  database_url="$(env_value MIEMIE_DATABASE_URL "$COMPOSE_ENV_FILE")"

  if [[ -z "$postgres_password" || "$postgres_password" == "replace-with-strong-password" ]]; then
    warn_or_block_for_compose "compose_env:postgres_password" "MIEMIE_POSTGRES_PASSWORD is missing or placeholder"
  else
    record_result "compose_env:postgres_password" "passed" "set"
  fi

  if [[ -z "$runtime_commit" || "$runtime_commit" == "replace-with-git-commit" ]]; then
    record_result "compose_env:runtime_commit" "warn" "MIEMIE_RUNTIME_GIT_COMMIT should be current git commit"
  else
    record_result "compose_env:runtime_commit" "passed" "set"
  fi

  if [[ "$host_bind" == "0.0.0.0" ]]; then
    record_result "compose_env:host_bind" "warn" "MIEMIE_HOST_BIND exposes app port directly; prefer 127.0.0.1 behind reverse proxy"
  else
    record_result "compose_env:host_bind" "passed" "${host_bind:-default}"
  fi

  if [[ "$database_enabled" == "true" && "$database_url" == *"replace-with"* ]]; then
    record_result "compose_env:database_url" "blocked" "database enabled while database URL still contains placeholder"
  fi
}

check_docker() {
  if ! profile_allows_compose; then
    return
  fi
  if ! command -v docker >/dev/null 2>&1; then
    warn_or_block_for_compose "docker" "docker missing"
    return
  fi
  record_result "docker" "passed" "$(docker --version 2>&1 | head -n 1)"
  log_cmd "docker-compose-version" docker compose version
  if docker compose version > "$ARTIFACT_DIR/docker-compose-version.txt" 2>&1; then
    record_result "docker_compose" "passed" "$(head -n 1 "$ARTIFACT_DIR/docker-compose-version.txt")"
  else
    warn_or_block_for_compose "docker_compose" "docker compose v2 unavailable"
  fi

  if [[ -f "$COMPOSE_ENV_FILE" ]]; then
    log_cmd "docker-compose-config" docker compose --env-file "$COMPOSE_ENV_FILE" config -q
    if docker compose --env-file "$COMPOSE_ENV_FILE" config -q > "$ARTIFACT_DIR/docker-compose-config.txt" 2>"$ARTIFACT_DIR/docker-compose-config.err"; then
      record_result "docker_compose_config" "passed" "config ok"
    else
      warn_or_block_for_compose "docker_compose_config" "docker compose config failed"
    fi
  fi

  if [[ "$MIEMIE_DEPLOY_DOCTOR_RUN_DOCKER_INFO" == "true" ]]; then
    log_cmd "docker-info" docker info
    if docker info > "$ARTIFACT_DIR/docker-info.txt" 2>"$ARTIFACT_DIR/docker-info.err"; then
      record_result "docker_daemon" "passed" "docker daemon reachable"
    else
      warn_or_block_for_compose "docker_daemon" "docker daemon unavailable"
    fi
  else
    record_result "docker_daemon" "warn" "skipped; set MIEMIE_DEPLOY_DOCTOR_RUN_DOCKER_INFO=true to check daemon"
  fi
}

check_sensitive_tracked_files() {
  local tracked
  tracked="$(git ls-files backend/data/config.json backend/data/users.json backend/data/sessions.json backend/data/users 2>/dev/null || true)"
  if [[ -n "$tracked" ]]; then
    printf '%s\n' "$tracked" > "$ARTIFACT_DIR/tracked-sensitive-files.txt"
    record_result "sensitive_tracked_files" "blocked" "sensitive backend/data files are tracked"
  else
    record_result "sensitive_tracked_files" "passed" "no tracked sensitive backend/data files"
  fi
}

check_ports() {
  if ! command -v lsof >/dev/null 2>&1; then
    record_result "ports" "warn" "lsof missing; cannot check local port occupancy"
    return
  fi
  local compose_port="8000"
  if [[ -f "$COMPOSE_ENV_FILE" ]]; then
    compose_port="$(env_value MIEMIE_HOST_PORT "$COMPOSE_ENV_FILE")"
    compose_port="${compose_port:-8000}"
  fi
  if lsof -tiTCP:"$compose_port" -sTCP:LISTEN >/dev/null 2>&1; then
    lsof -nP -iTCP:"$compose_port" -sTCP:LISTEN > "$ARTIFACT_DIR/port-$compose_port.txt" 2>/dev/null || true
    record_result "port:$compose_port" "warn" "port already has a listener"
  else
    record_result "port:$compose_port" "passed" "available"
  fi
}

main() {
  if [[ "$MIEMIE_DEPLOY_DOCTOR_DRY_RUN" == "true" ]]; then
    record_result "dry_run" "passed" "no checks executed"
    write_status "dry_run" "planned" "set MIEMIE_DEPLOY_DOCTOR_DRY_RUN=false to execute checks"
    return 0
  fi

  date -u +%Y-%m-%dT%H:%M:%SZ > "$ARTIFACT_DIR/time.txt"
  git rev-parse HEAD > "$ARTIFACT_DIR/git-head.txt" 2>/dev/null || true
  git status --short > "$ARTIFACT_DIR/git-status-short.txt" 2>/dev/null || true

  case "$DOCTOR_PROFILE" in
    all|script|compose) ;;
    *)
      record_result "profile" "blocked" "unsupported DOCTOR_PROFILE=$DOCTOR_PROFILE"
      write_status "blocked" "precheck" "unsupported DOCTOR_PROFILE"
      return 2
      ;;
  esac
  record_result "profile" "passed" "$DOCTOR_PROFILE"

  check_command_exists "git" "git" "true"
  check_python
  check_node
  check_command_exists "npm" "npm" "true"
  check_command_exists "curl" "curl" "true"
  check_command_exists "screen" "screen" "false"
  check_command_exists "lsof" "lsof" "false"
  check_required_files
  check_sensitive_tracked_files
  check_compose_env
  check_docker
  check_ports

  if [[ "$BLOCKED" -gt 0 || "$FAILED" -gt 0 ]]; then
    write_status "blocked" "done" "$BLOCKED blocked, $FAILED failed, $WARNED warnings"
    return 2
  fi
  if [[ "$WARNED" -gt 0 ]]; then
    write_status "passed_with_warnings" "done" "$WARNED warnings"
    return 0
  fi
  write_status "passed" "done" ""
}

main "$@"
