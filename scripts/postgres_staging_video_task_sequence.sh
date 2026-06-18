#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-postgres-staging-video-task-sequence-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r51-staging-video-task-sequence}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
CANARY_SCRIPT="${CANARY_SCRIPT:-$ROOT_DIR/scripts/postgres_staging_video_task_canary.sh}"
ALL_DOMAIN_CANARY_SCRIPT="${ALL_DOMAIN_CANARY_SCRIPT:-$ROOT_DIR/scripts/postgres_staging_all_domain_canary.sh}"
LIVE_DATA_GATE_SCRIPT="${LIVE_DATA_GATE_SCRIPT:-$ROOT_DIR/scripts/postgres_staging_live_data_gate.sh}"
CONFIRM_STAGING_SEQUENCE="${CONFIRM_STAGING_SEQUENCE:-dry-run}"
SEQUENCE="${SEQUENCE:-audit roll-runtime live-data-gate all-domain-dual-write-canary all-domain-read-switch-canary all-domain-rollback-read-switch all-domain-primary-write-canary all-domain-rollback-primary-write}"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
RESULTS_FILE="$ARTIFACT_DIR/results.tsv"
SEQUENCE_FILE="$ARTIFACT_DIR/sequence.txt"
: > "$COMMAND_LOG"
: > "$RESULTS_FILE"
printf 'index\tmode\texit_code\tstate\tartifact_dir\n' > "$RESULTS_FILE"

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
  "sequence": "$(json_escape "$SEQUENCE")",
  "confirm": "$(json_escape "$CONFIRM_STAGING_SEQUENCE")",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
}

log_line() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$COMMAND_LOG"
}

stage_state_for_exit() {
  local exit_code="$1"
  if [[ "$exit_code" == "0" ]]; then
    printf 'passed'
  elif [[ "$exit_code" == "2" ]]; then
    printf 'blocked'
  else
    printf 'failed'
  fi
}

write_sequence_file() {
  : > "$SEQUENCE_FILE"
  local index=0
  local mode
  for mode in $SEQUENCE; do
    index=$((index + 1))
    printf '%02d %s\n' "$index" "$mode" >> "$SEQUENCE_FILE"
  done
}

run_stage() {
  local index="$1"
  local mode="$2"
  local stage_dir="$ARTIFACT_DIR/$(printf '%02d' "$index")-$mode"
  local stage_tmp="$TMP_DIR/$(printf '%02d' "$index")-$mode"
  local exit_code state
  mkdir -p "$stage_dir" "$stage_tmp"

  log_line "stage=$index mode=$mode artifact_dir=$stage_dir"

  set +e
  if [[ "$mode" == "live-data-gate" ]]; then
    log_line "+ CONFIRM_LIVE_DATA_GATE=run RUN_ID=${RUN_ID}-${index}-${mode} ARTIFACT_DIR=$stage_dir TMP_DIR=$stage_tmp bash $LIVE_DATA_GATE_SCRIPT"
    CONFIRM_LIVE_DATA_GATE=run \
      RUN_ID="${RUN_ID}-${index}-${mode}" \
      ARTIFACT_DIR="$stage_dir" \
      TMP_DIR="$stage_tmp" \
      bash "$LIVE_DATA_GATE_SCRIPT" >> "$COMMAND_LOG" 2>&1
  elif [[ "$mode" == all-domain-* ]]; then
    log_line "+ MODE=$mode CONFIRM_ALL_DOMAIN_CANARY=run RUN_ID=${RUN_ID}-${index}-${mode} ARTIFACT_DIR=$stage_dir TMP_DIR=$stage_tmp bash $ALL_DOMAIN_CANARY_SCRIPT"
    MODE="$mode" \
      CONFIRM_ALL_DOMAIN_CANARY=run \
      RUN_ID="${RUN_ID}-${index}-${mode}" \
      ARTIFACT_DIR="$stage_dir" \
      TMP_DIR="$stage_tmp" \
      bash "$ALL_DOMAIN_CANARY_SCRIPT" >> "$COMMAND_LOG" 2>&1
  else
    log_line "+ MODE=$mode RUN_ID=${RUN_ID}-${index}-${mode} ARTIFACT_DIR=$stage_dir TMP_DIR=$stage_tmp bash $CANARY_SCRIPT"
    MODE="$mode" \
      RUN_ID="${RUN_ID}-${index}-${mode}" \
      ARTIFACT_DIR="$stage_dir" \
      TMP_DIR="$stage_tmp" \
      bash "$CANARY_SCRIPT" >> "$COMMAND_LOG" 2>&1
  fi
  exit_code=$?
  set -e

  state="$(stage_state_for_exit "$exit_code")"
  printf '%s\t%s\t%s\t%s\t%s\n' "$index" "$mode" "$exit_code" "$state" "$stage_dir" >> "$RESULTS_FILE"
  if [[ "$exit_code" != "0" ]]; then
    write_status "$state" "$mode" "stage $mode exited with $exit_code"
    exit "$exit_code"
  fi
}

main() {
  write_sequence_file
  [[ -f "$CANARY_SCRIPT" ]] || {
    write_status "blocked" "precheck" "missing canary script: $CANARY_SCRIPT"
    printf 'missing canary script: %s\n' "$CANARY_SCRIPT" >&2
    exit 2
  }
  [[ -f "$ALL_DOMAIN_CANARY_SCRIPT" ]] || {
    write_status "blocked" "precheck" "missing all-domain canary script: $ALL_DOMAIN_CANARY_SCRIPT"
    printf 'missing all-domain canary script: %s\n' "$ALL_DOMAIN_CANARY_SCRIPT" >&2
    exit 2
  }
  [[ -f "$LIVE_DATA_GATE_SCRIPT" ]] || {
    write_status "blocked" "precheck" "missing live data gate script: $LIVE_DATA_GATE_SCRIPT"
    printf 'missing live data gate script: %s\n' "$LIVE_DATA_GATE_SCRIPT" >&2
    exit 2
  }

  if [[ "$CONFIRM_STAGING_SEQUENCE" != "run" ]]; then
    write_status "dry_run" "planned" "set CONFIRM_STAGING_SEQUENCE=run to execute"
    log_line "dry-run only; no canary stage executed"
    printf 'dry-run sequence written to %s\n' "$SEQUENCE_FILE"
    exit 0
  fi

  write_status "running" "sequence" ""
  local index=0
  local mode
  for mode in $SEQUENCE; do
    index=$((index + 1))
    run_stage "$index" "$mode"
  done
  write_status "passed" "done" ""
}

main "$@"
