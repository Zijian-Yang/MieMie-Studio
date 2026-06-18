#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-pre-studio-server-postgres-final-exit-sequence-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/validation-artifacts/$RUN_ID}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
CONFIRM_SERVER_FINAL_EXIT_SEQUENCE="${CONFIRM_SERVER_FINAL_EXIT_SEQUENCE:-dry-run}"
FINAL_EXIT_ROLLBACK_ON_FAILURE="${FINAL_EXIT_ROLLBACK_ON_FAILURE:-true}"
ENV_FILE="${ENV_FILE:-compose.env}"
SERVER_SYNC="${SERVER_SYNC:-ff-only}"
SERVER_SEQUENCE_ARTIFACT_DIR="${SERVER_SEQUENCE_ARTIFACT_DIR:-$ARTIFACT_DIR/server-sequence}"
SEQUENCE_ARTIFACT_DIR="${SEQUENCE_ARTIFACT_DIR:-$SERVER_SEQUENCE_ARTIFACT_DIR/sequence}"
APPLY_ARTIFACT_DIR="${APPLY_ARTIFACT_DIR:-$ARTIFACT_DIR/apply-final-json-exit-policy}"
POST_VALIDATION_ARTIFACT_DIR="${POST_VALIDATION_ARTIFACT_DIR:-$ARTIFACT_DIR/post-json-exit-validation}"
ROLLBACK_ARTIFACT_DIR="${ROLLBACK_ARTIFACT_DIR:-$ARTIFACT_DIR/rollback-final-json-exit-policy}"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
PLAN_FILE="$ARTIFACT_DIR/server-final-exit-sequence-plan.sh"
: > "$COMMAND_LOG"

if [[ -x "backend/.venv/bin/python" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-backend/.venv/bin/python}"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON_BIN:-python3}"
else
  PYTHON_BIN="${PYTHON_BIN:-}"
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
  "confirm": "$(json_escape "$CONFIRM_SERVER_FINAL_EXIT_SEQUENCE")",
  "rollback_on_failure": "$(json_escape "$FINAL_EXIT_ROLLBACK_ON_FAILURE")",
  "env_file": "$(json_escape "$ENV_FILE")",
  "server_sync": "$(json_escape "$SERVER_SYNC")",
  "server_sequence_artifact_dir": "$(json_escape "$SERVER_SEQUENCE_ARTIFACT_DIR")",
  "sequence_artifact_dir": "$(json_escape "$SEQUENCE_ARTIFACT_DIR")",
  "apply_artifact_dir": "$(json_escape "$APPLY_ARTIFACT_DIR")",
  "post_validation_artifact_dir": "$(json_escape "$POST_VALIDATION_ARTIFACT_DIR")",
  "rollback_artifact_dir": "$(json_escape "$ROLLBACK_ARTIFACT_DIR")",
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

write_plan() {
  cat > "$PLAN_FILE" <<PLAN
#!/usr/bin/env bash
set -Eeuo pipefail

# Planned server-side final JSON exit sequence. The real run is gated by CONFIRM_SERVER_FINAL_EXIT_SEQUENCE=run.
CONFIRM_SERVER_SEQUENCE=run \\
  RUN_ID="$RUN_ID-server-sequence" \\
  ARTIFACT_DIR="$SERVER_SEQUENCE_ARTIFACT_DIR" \\
  TMP_DIR="$TMP_DIR/server-sequence" \\
  SERVER_SYNC="$SERVER_SYNC" \\
  bash scripts/pre_studio_server_postgres_sequence.sh

SEQUENCE_ARTIFACT_DIR="$SEQUENCE_ARTIFACT_DIR"

CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY=run \\
  RUN_ID="$RUN_ID-apply-final-json-exit-policy" \\
  ARTIFACT_DIR="$APPLY_ARTIFACT_DIR" \\
  TMP_DIR="$TMP_DIR/apply-final-json-exit-policy" \\
  ENV_FILE="$ENV_FILE" \\
  SEQUENCE_ARTIFACT_DIR="\$SEQUENCE_ARTIFACT_DIR" \\
  bash scripts/postgres_apply_final_json_exit_policy.sh

CONFIRM_POST_JSON_EXIT_VALIDATION=run \\
  RUN_ID="$RUN_ID-post-json-exit-validation" \\
  ARTIFACT_DIR="$POST_VALIDATION_ARTIFACT_DIR" \\
  TMP_DIR="$TMP_DIR/post-json-exit-validation" \\
  ENV_FILE="$ENV_FILE" \\
  SEQUENCE_ARTIFACT_DIR="\$SEQUENCE_ARTIFACT_DIR" \\
  bash scripts/postgres_post_json_exit_validation.sh

ROLLBACK_ENV_BACKUP_FILE="\$(find "$APPLY_ARTIFACT_DIR" -maxdepth 1 -name 'compose.env.before-final-json-exit.*.bak' -print | sort | tail -n 1)"
CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY=run \\
  RUN_ID="$RUN_ID-rollback-final-json-exit-policy" \\
  ARTIFACT_DIR="$ROLLBACK_ARTIFACT_DIR" \\
  TMP_DIR="$TMP_DIR/rollback-final-json-exit-policy" \\
  ENV_FILE="$ENV_FILE" \\
  ROLLBACK_ENV_BACKUP_FILE="\$ROLLBACK_ENV_BACKUP_FILE" \\
  bash scripts/postgres_rollback_final_json_exit_policy.sh
PLAN
}

verify_preconditions() {
  [[ -n "$PYTHON_BIN" ]] || blocked "precheck" "python unavailable"
  [[ -f scripts/pre_studio_server_postgres_sequence.sh ]] || blocked "precheck" "missing pre_studio_server_postgres_sequence.sh"
  [[ -f scripts/postgres_apply_final_json_exit_policy.sh ]] || blocked "precheck" "missing postgres_apply_final_json_exit_policy.sh"
  [[ -f scripts/postgres_post_json_exit_validation.sh ]] || blocked "precheck" "missing postgres_post_json_exit_validation.sh"
  [[ -f scripts/postgres_rollback_final_json_exit_policy.sh ]] || blocked "precheck" "missing postgres_rollback_final_json_exit_policy.sh"
}

check_status_state() {
  local file="$1"
  local expected="$2"
  [[ -f "$file" ]] || return 1
  "$PYTHON_BIN" - "$file" "$expected" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    status = json.load(handle)
if status.get("state") != sys.argv[2]:
    raise SystemExit(f"unexpected state: {status.get('state')!r}")
PY
}

find_rollback_backup() {
  local candidate
  for candidate in "$APPLY_ARTIFACT_DIR"/compose.env.before-final-json-exit.*.bak; do
    if [[ -f "$candidate" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

run_rollback() {
  if [[ "$FINAL_EXIT_ROLLBACK_ON_FAILURE" != "true" ]]; then
    return 3
  fi

  local backup_file
  backup_file="$(find_rollback_backup || true)"
  if [[ -z "$backup_file" ]]; then
    return 4
  fi

  log_cmd "rollback-final-json-exit-policy" \
    bash scripts/postgres_rollback_final_json_exit_policy.sh
  CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY=run \
    RUN_ID="$RUN_ID-rollback-final-json-exit-policy" \
    ARTIFACT_DIR="$ROLLBACK_ARTIFACT_DIR" \
    TMP_DIR="$TMP_DIR/rollback-final-json-exit-policy" \
    ENV_FILE="$ENV_FILE" \
    ROLLBACK_ENV_BACKUP_FILE="$backup_file" \
    bash scripts/postgres_rollback_final_json_exit_policy.sh >> "$COMMAND_LOG" 2>&1
}

handle_failure() {
  local stage="$1"
  local exit_code="$2"
  if [[ "$stage" == "apply-final-json-exit-policy" || "$stage" == "post-json-exit-validation" ]]; then
    set +e
    run_rollback
    local rollback_code=$?
    set -e
    if [[ "$rollback_code" == "0" ]]; then
      failed "$stage" "$stage failed with exit code $exit_code; rollback passed"
    elif [[ "$rollback_code" == "3" ]]; then
      failed "$stage" "$stage failed with exit code $exit_code; rollback disabled"
    elif [[ "$rollback_code" == "4" ]]; then
      failed "$stage" "$stage failed with exit code $exit_code; rollback backup missing"
    else
      failed "$stage" "$stage failed with exit code $exit_code; rollback failed with exit code $rollback_code"
    fi
  fi
  failed "$stage" "$stage failed with exit code $exit_code"
}

run_server_sequence() {
  write_status "running" "server-sequence" ""
  set +e
  CONFIRM_SERVER_SEQUENCE=run \
    RUN_ID="$RUN_ID-server-sequence" \
    ARTIFACT_DIR="$SERVER_SEQUENCE_ARTIFACT_DIR" \
    TMP_DIR="$TMP_DIR/server-sequence" \
    SERVER_SYNC="$SERVER_SYNC" \
    bash scripts/pre_studio_server_postgres_sequence.sh >> "$COMMAND_LOG" 2>&1
  local exit_code=$?
  set -e
  [[ "$exit_code" == "0" ]] || handle_failure "server-sequence" "$exit_code"
  check_status_state "$SERVER_SEQUENCE_ARTIFACT_DIR/status.json" "passed" || failed "server-sequence" "server sequence status is not passed"
}

run_apply_final_policy() {
  write_status "running" "apply-final-json-exit-policy" ""
  set +e
  CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY=run \
    RUN_ID="$RUN_ID-apply-final-json-exit-policy" \
    ARTIFACT_DIR="$APPLY_ARTIFACT_DIR" \
    TMP_DIR="$TMP_DIR/apply-final-json-exit-policy" \
    ENV_FILE="$ENV_FILE" \
    SEQUENCE_ARTIFACT_DIR="$SEQUENCE_ARTIFACT_DIR" \
    bash scripts/postgres_apply_final_json_exit_policy.sh >> "$COMMAND_LOG" 2>&1
  local exit_code=$?
  set -e
  [[ "$exit_code" == "0" ]] || handle_failure "apply-final-json-exit-policy" "$exit_code"
  check_status_state "$APPLY_ARTIFACT_DIR/status.json" "passed" || handle_failure "apply-final-json-exit-policy" 1
}

run_post_validation() {
  write_status "running" "post-json-exit-validation" ""
  set +e
  CONFIRM_POST_JSON_EXIT_VALIDATION=run \
    RUN_ID="$RUN_ID-post-json-exit-validation" \
    ARTIFACT_DIR="$POST_VALIDATION_ARTIFACT_DIR" \
    TMP_DIR="$TMP_DIR/post-json-exit-validation" \
    ENV_FILE="$ENV_FILE" \
    SEQUENCE_ARTIFACT_DIR="$SEQUENCE_ARTIFACT_DIR" \
    bash scripts/postgres_post_json_exit_validation.sh >> "$COMMAND_LOG" 2>&1
  local exit_code=$?
  set -e
  [[ "$exit_code" == "0" ]] || handle_failure "post-json-exit-validation" "$exit_code"
  check_status_state "$POST_VALIDATION_ARTIFACT_DIR/status.json" "passed" || handle_failure "post-json-exit-validation" 1
}

main() {
  write_plan
  if [[ "$CONFIRM_SERVER_FINAL_EXIT_SEQUENCE" != "run" ]]; then
    write_status "dry_run" "planned" "set CONFIRM_SERVER_FINAL_EXIT_SEQUENCE=run to execute on the server"
    printf 'dry-run server final exit sequence plan written to %s\n' "$PLAN_FILE"
    return 0
  fi

  write_status "running" "precheck" ""
  verify_preconditions
  run_server_sequence
  run_apply_final_policy
  run_post_validation
  write_status "passed" "done" ""
}

main "$@"
