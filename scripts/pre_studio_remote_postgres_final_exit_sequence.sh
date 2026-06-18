#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-pre-studio-remote-postgres-final-exit-sequence-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r85-remote-final-exit-sequence}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-12}"
SSH_TARGET="${SSH_TARGET:-root@47.79.99.190}"
SSH_PORT="${SSH_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:-/opt/miemie-pre}"
REMOTE_BRANCH="${REMOTE_BRANCH:-pre}"
REMOTE_ARTIFACT_DIR="${REMOTE_ARTIFACT_DIR:-$REMOTE_DIR/validation-artifacts/$RUN_ID}"
REMOTE_TMP_DIR="${REMOTE_TMP_DIR:-/tmp/$RUN_ID}"
REMOTE_RUNNER="${REMOTE_RUNNER:-scripts/pre_studio_server_postgres_final_exit_sequence.sh}"
LOCAL_PREFLIGHT_SCRIPT="${LOCAL_PREFLIGHT_SCRIPT:-$ROOT_DIR/scripts/pre_studio_connectivity_preflight.sh}"
CONFIRM_REMOTE_FINAL_EXIT_SEQUENCE="${CONFIRM_REMOTE_FINAL_EXIT_SEQUENCE:-dry-run}"
REMOTE_SYNC="${REMOTE_SYNC:-ff-only}"
FINAL_EXIT_ROLLBACK_ON_FAILURE="${FINAL_EXIT_ROLLBACK_ON_FAILURE:-true}"
PULL_REMOTE_ARTIFACTS="${PULL_REMOTE_ARTIFACTS:-true}"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
REMOTE_COMMAND_FILE="$ARTIFACT_DIR/remote-command.sh"
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
  cat > "$STATUS_FILE" <<JSON
{
  "run_id": "$(json_escape "$RUN_ID")",
  "state": "$(json_escape "$state")",
  "stage": "$(json_escape "$stage")",
  "reason": "$(json_escape "$reason")",
  "ssh_target": "$(json_escape "$SSH_TARGET")",
  "remote_dir": "$(json_escape "$REMOTE_DIR")",
  "remote_branch": "$(json_escape "$REMOTE_BRANCH")",
  "remote_artifact_dir": "$(json_escape "$REMOTE_ARTIFACT_DIR")",
  "remote_sync": "$(json_escape "$REMOTE_SYNC")",
  "rollback_on_failure": "$(json_escape "$FINAL_EXIT_ROLLBACK_ON_FAILURE")",
  "confirm": "$(json_escape "$CONFIRM_REMOTE_FINAL_EXIT_SEQUENCE")",
  "artifact_dir": "$(json_escape "$ARTIFACT_DIR")",
  "tmp_dir": "$(json_escape "$TMP_DIR")",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
}

log_line() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$COMMAND_LOG"
}

build_remote_command() {
  local quoted_remote_dir quoted_branch quoted_run_id quoted_artifact_dir quoted_tmp_dir quoted_runner quoted_rollback
  quoted_remote_dir="$(shell_quote "$REMOTE_DIR")"
  quoted_branch="$(shell_quote "$REMOTE_BRANCH")"
  quoted_run_id="$(shell_quote "$RUN_ID")"
  quoted_artifact_dir="$(shell_quote "$REMOTE_ARTIFACT_DIR")"
  quoted_tmp_dir="$(shell_quote "$REMOTE_TMP_DIR")"
  quoted_runner="$(shell_quote "$REMOTE_RUNNER")"
  quoted_rollback="$(shell_quote "$FINAL_EXIT_ROLLBACK_ON_FAILURE")"

  {
    printf 'set -Eeuo pipefail\n'
    printf 'cd %s\n' "$quoted_remote_dir"
    printf 'git rev-parse --abbrev-ref HEAD\n'
    printf 'git status --short\n'
    if [[ "$REMOTE_SYNC" == "ff-only" ]]; then
      printf 'git fetch origin %s\n' "$quoted_branch"
      printf 'git merge --ff-only origin/%s\n' "$quoted_branch"
    elif [[ "$REMOTE_SYNC" == "none" ]]; then
      printf 'printf %%s\\\\n "remote sync skipped"\n'
    else
      printf 'printf %%s\\\\n "unsupported REMOTE_SYNC=%s" >&2\n' "$(shell_quote "$REMOTE_SYNC")"
      printf 'exit 64\n'
    fi
    printf 'test -f %s\n' "$quoted_runner"
    printf 'CONFIRM_SERVER_FINAL_EXIT_SEQUENCE=run SERVER_SYNC=none FINAL_EXIT_ROLLBACK_ON_FAILURE=%s RUN_ID=%s ARTIFACT_DIR=%s TMP_DIR=%s bash %s\n' \
      "$quoted_rollback" "$quoted_run_id" "$quoted_artifact_dir" "$quoted_tmp_dir" "$quoted_runner"
  } > "$REMOTE_COMMAND_FILE"
}

run_local_preflight() {
  [[ -f "$LOCAL_PREFLIGHT_SCRIPT" ]] || {
    write_status "blocked" "preflight" "missing local preflight script: $LOCAL_PREFLIGHT_SCRIPT"
    return 2
  }
  log_line "+ RUN_ID=${RUN_ID}-preflight ARTIFACT_DIR=$ARTIFACT_DIR/preflight TMP_DIR=$TMP_DIR/preflight bash $LOCAL_PREFLIGHT_SCRIPT"
  set +e
  RUN_ID="${RUN_ID}-preflight" \
    ARTIFACT_DIR="$ARTIFACT_DIR/preflight" \
    TMP_DIR="$TMP_DIR/preflight" \
    bash "$LOCAL_PREFLIGHT_SCRIPT" >> "$COMMAND_LOG" 2>&1
  local exit_code=$?
  set -e
  if [[ "$exit_code" != "0" ]]; then
    write_status "blocked" "preflight" "local connectivity preflight exited with $exit_code"
    return 2
  fi
}

run_remote_final_exit_sequence() {
  local remote_command exit_code
  remote_command="$(cat "$REMOTE_COMMAND_FILE")"
  log_line "+ ssh -o BatchMode=yes -o ConnectTimeout=$CONNECT_TIMEOUT -o StrictHostKeyChecking=accept-new -p $SSH_PORT $SSH_TARGET <remote-command>"
  set +e
  ssh -o BatchMode=yes -o ConnectTimeout="$CONNECT_TIMEOUT" -o StrictHostKeyChecking=accept-new -p "$SSH_PORT" "$SSH_TARGET" "$remote_command" \
    > "$ARTIFACT_DIR/remote-final-exit-sequence.out" 2>"$ARTIFACT_DIR/remote-final-exit-sequence.err"
  exit_code=$?
  set -e
  if [[ "$exit_code" != "0" ]]; then
    write_status "failed" "remote-final-exit-sequence" "remote final exit sequence exited with $exit_code"
    return "$exit_code"
  fi
}

pull_remote_artifacts() {
  if [[ "$PULL_REMOTE_ARTIFACTS" != "true" ]]; then
    log_line "remote artifact pull skipped"
    return 0
  fi
  mkdir -p "$ARTIFACT_DIR/remote-artifacts"
  log_line "+ scp -r $SSH_TARGET:$REMOTE_ARTIFACT_DIR $ARTIFACT_DIR/remote-artifacts/"
  scp -P "$SSH_PORT" -o BatchMode=yes -o ConnectTimeout="$CONNECT_TIMEOUT" -o StrictHostKeyChecking=accept-new \
    -r "$SSH_TARGET:$REMOTE_ARTIFACT_DIR" "$ARTIFACT_DIR/remote-artifacts/" \
    >> "$COMMAND_LOG" 2>&1 || {
    log_line "remote artifact pull failed; leaving server-side artifact path in status"
    return 0
  }
}

main() {
  build_remote_command
  if [[ "$CONFIRM_REMOTE_FINAL_EXIT_SEQUENCE" != "run" ]]; then
    write_status "dry_run" "planned" "set CONFIRM_REMOTE_FINAL_EXIT_SEQUENCE=run to execute local preflight and remote final exit sequence"
    log_line "dry-run only; execution skipped"
    printf 'dry-run remote final exit command written to %s\n' "$REMOTE_COMMAND_FILE"
    return 0
  fi

  write_status "running" "preflight" ""
  run_local_preflight
  write_status "running" "remote-final-exit-sequence" ""
  run_remote_final_exit_sequence
  pull_remote_artifacts
  write_status "passed" "done" ""
}

main "$@"
