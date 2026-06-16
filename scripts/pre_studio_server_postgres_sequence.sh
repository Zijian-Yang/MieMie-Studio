#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-pre-studio-server-postgres-sequence-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/validation-artifacts/$RUN_ID}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
SERVER_BRANCH="${SERVER_BRANCH:-pre}"
SERVER_SYNC="${SERVER_SYNC:-ff-only}"
SEQUENCE_RUNNER="${SEQUENCE_RUNNER:-scripts/postgres_staging_video_task_sequence.sh}"
CONFIRM_SERVER_SEQUENCE="${CONFIRM_SERVER_SEQUENCE:-dry-run}"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
PLAN_FILE="$ARTIFACT_DIR/server-sequence-plan.sh"
: > "$COMMAND_LOG"

if [[ -x "backend/.venv/bin/python" ]]; then
  JSON_PYTHON="backend/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  JSON_PYTHON="python3"
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

shell_quote() {
  printf '%q' "$1"
}

write_status() {
  local state="$1"
  local stage="$2"
  local reason="${3:-}"
  local branch head
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || printf unknown)"
  head="$(git rev-parse HEAD 2>/dev/null || printf unknown)"
  cat > "$STATUS_FILE" <<JSON
{
  "run_id": "$(json_escape "$RUN_ID")",
  "state": "$(json_escape "$state")",
  "stage": "$(json_escape "$stage")",
  "reason": "$(json_escape "$reason")",
  "branch": "$(json_escape "$branch")",
  "head": "$(json_escape "$head")",
  "server_branch": "$(json_escape "$SERVER_BRANCH")",
  "server_sync": "$(json_escape "$SERVER_SYNC")",
  "confirm": "$(json_escape "$CONFIRM_SERVER_SEQUENCE")",
  "sequence_runner": "$(json_escape "$SEQUENCE_RUNNER")",
  "artifact_dir": "$(json_escape "$ARTIFACT_DIR")",
  "tmp_dir": "$(json_escape "$TMP_DIR")",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
}

log_line() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$COMMAND_LOG"
}

run_logged() {
  log_line "+ $*"
  "$@" >> "$COMMAND_LOG" 2>&1
}

blocked() {
  local stage="$1"
  local reason="$2"
  write_status "blocked" "$stage" "$reason"
  printf 'blocked: %s\n' "$reason" >&2
  exit 2
}

failed() {
  local stage="$1"
  local reason="$2"
  write_status "failed" "$stage" "$reason"
  printf 'failed: %s\n' "$reason" >&2
  exit 1
}

write_plan() {
  {
    printf 'set -Eeuo pipefail\n'
    printf 'cd %s\n' "$(shell_quote "$ROOT_DIR")"
    printf 'git rev-parse --abbrev-ref HEAD\n'
    printf 'git status --short\n'
    if [[ "$SERVER_SYNC" == "ff-only" ]]; then
      printf 'git fetch origin %s\n' "$(shell_quote "$SERVER_BRANCH")"
      printf 'git merge --ff-only origin/%s\n' "$(shell_quote "$SERVER_BRANCH")"
    elif [[ "$SERVER_SYNC" == "none" ]]; then
      printf 'printf %%s\\\\n "server sync skipped"\n'
    else
      printf 'printf %%s\\\\n "unsupported SERVER_SYNC=%s" >&2\n' "$(shell_quote "$SERVER_SYNC")"
      printf 'exit 64\n'
    fi
    printf 'test -f %s\n' "$(shell_quote "$SEQUENCE_RUNNER")"
    printf 'CONFIRM_STAGING_SEQUENCE=run RUN_ID=%s ARTIFACT_DIR=%s TMP_DIR=%s bash %s\n' \
      "$(shell_quote "$RUN_ID")" "$(shell_quote "$ARTIFACT_DIR/sequence")" "$(shell_quote "$TMP_DIR/sequence")" "$(shell_quote "$SEQUENCE_RUNNER")"
  } > "$PLAN_FILE"
}

verify_server_context() {
  command -v git >/dev/null 2>&1 || blocked "precheck" "git unavailable"
  [[ -n "$JSON_PYTHON" ]] || blocked "precheck" "python unavailable"
  [[ -f docker-compose.yml ]] || blocked "precheck" "missing docker-compose.yml"
  [[ -f compose.env ]] || blocked "precheck" "missing compose.env"
  [[ -f docker-compose.pre.override.yml ]] || blocked "precheck" "missing docker-compose.pre.override.yml"
  [[ -f "$SEQUENCE_RUNNER" ]] || blocked "precheck" "missing sequence runner: $SEQUENCE_RUNNER"
  local branch
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  [[ "$branch" == "$SERVER_BRANCH" ]] || blocked "precheck" "expected branch $SERVER_BRANCH, got ${branch:-unknown}"
}

execute_plan() {
  case "$SERVER_SYNC" in
    ff-only)
      run_logged git fetch origin "$SERVER_BRANCH" || failed "sync" "git fetch origin $SERVER_BRANCH failed"
      run_logged git merge --ff-only "origin/$SERVER_BRANCH" || failed "sync" "git merge --ff-only origin/$SERVER_BRANCH failed"
      ;;
    none)
      log_line "server sync skipped"
      ;;
    *)
      blocked "precheck" "unsupported SERVER_SYNC=$SERVER_SYNC"
      ;;
  esac

  [[ -f "$SEQUENCE_RUNNER" ]] || blocked "precheck" "missing sequence runner after sync: $SEQUENCE_RUNNER"
  log_line "+ CONFIRM_STAGING_SEQUENCE=run RUN_ID=$RUN_ID ARTIFACT_DIR=$ARTIFACT_DIR/sequence TMP_DIR=$TMP_DIR/sequence bash $SEQUENCE_RUNNER"
  set +e
  CONFIRM_STAGING_SEQUENCE=run \
    RUN_ID="$RUN_ID" \
    ARTIFACT_DIR="$ARTIFACT_DIR/sequence" \
    TMP_DIR="$TMP_DIR/sequence" \
    bash "$SEQUENCE_RUNNER" >> "$COMMAND_LOG" 2>&1
  local exit_code=$?
  set -e
  if [[ "$exit_code" != "0" ]]; then
    if [[ "$exit_code" == "2" ]]; then
      blocked "sequence" "sequence runner blocked with exit code 2"
    fi
    failed "sequence" "sequence runner failed with exit code $exit_code"
  fi
}

main() {
  write_plan
  if [[ "$CONFIRM_SERVER_SEQUENCE" != "run" ]]; then
    write_status "dry_run" "planned" "set CONFIRM_SERVER_SEQUENCE=run to execute on the server"
    log_line "dry-run only; server sequence plan written to $PLAN_FILE"
    printf 'dry-run server sequence plan written to %s\n' "$PLAN_FILE"
    return 0
  fi

  write_status "running" "precheck" ""
  verify_server_context
  write_status "running" "sequence" ""
  execute_plan
  write_status "passed" "done" ""
}

main "$@"
