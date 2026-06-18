#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-postgres-apply-final-json-exit-policy-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r82-apply-final-json-exit-policy}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY="${CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY:-dry-run}"
ENV_FILE="${ENV_FILE:-compose.env}"
SEQUENCE_ARTIFACT_DIR="${SEQUENCE_ARTIFACT_DIR:-}"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
PLAN_FILE="$ARTIFACT_DIR/apply-final-json-exit-policy-plan.sh"
FINAL_ENV_FILE="$ARTIFACT_DIR/compose.env.final-policy.sanitized"
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
  "confirm": "$(json_escape "$CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY")",
  "env_file": "$(json_escape "$ENV_FILE")",
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

set_env_value() {
  local key="$1"
  local value="$2"
  local target="${3:-$ENV_FILE}"
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
  ' "$target" > "$tmp_file"
  cat "$tmp_file" > "$target"
  rm -f "$tmp_file"
}

redact_env_file() {
  local input="$1"
  local output="$2"
  grep -E '^(MIEMIE_RUNTIME_GIT_COMMIT|MIEMIE_HOST|MIEMIE_WORKERS|MIEMIE_TASK|MIEMIE_VIDEO|MIEMIE_DATABASE|MIEMIE_POSTGRES)' "$input" \
    | sed -E \
      -e 's/(MIEMIE_POSTGRES_PASSWORD=).*/\1<redacted>/' \
      -e 's#(MIEMIE_DATABASE_URL=postgresql\+psycopg://miemie:)[^@]+#\1<redacted>#' \
    > "$output"
}

apply_final_policy_to_file() {
  local target="$1"
  set_env_value MIEMIE_DATABASE_ENABLED true "$target"
  set_env_value MIEMIE_DATABASE_WRITE_MODE postgres "$target"
  set_env_value MIEMIE_DATABASE_READ_MODE postgres "$target"
  set_env_value MIEMIE_DATABASE_DUAL_WRITE_DOMAINS "" "$target"
  set_env_value MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS "" "$target"
  set_env_value MIEMIE_DATABASE_READ_DOMAINS "" "$target"
  set_env_value MIEMIE_DATABASE_JSON_FALLBACK_READ false "$target"
  set_env_value MIEMIE_DATABASE_JSON_ARCHIVE_WRITES false "$target"
  set_env_value MIEMIE_DATABASE_RECONCILE_STRICT true "$target"
}

write_plan() {
  local backup_file
  backup_file="$ARTIFACT_DIR/compose.env.before-final-json-exit.$RUN_ID.bak"
  cat > "$PLAN_FILE" <<PLAN
#!/usr/bin/env bash
set -Eeuo pipefail

# Planned final JSON exit policy application. The real run is gated by CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY=run.
BACKUP_FILE="$backup_file"
cp "\$ENV_FILE" "\$BACKUP_FILE"
MIEMIE_DATABASE_ENABLED=true
MIEMIE_DATABASE_WRITE_MODE=postgres
MIEMIE_DATABASE_READ_MODE=postgres
MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=
MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=
MIEMIE_DATABASE_READ_DOMAINS=
MIEMIE_DATABASE_JSON_FALLBACK_READ=false
MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false
MIEMIE_DATABASE_RECONCILE_STRICT=true
python3 scripts/postgres_final_json_exit_audit.py --sequence-artifact-dir "\$SEQUENCE_ARTIFACT_DIR" --env-file "\$ENV_FILE" --artifact-dir "\$ARTIFACT_DIR/final-json-exit-audit"
grep -q ready_for_post_json_exit_validation "\$ARTIFACT_DIR/final-json-exit-audit/status.json"
PLAN
}

write_sanitized_final_env_preview() {
  local preview_file="$TMP_DIR/compose.env.final-policy.preview"
  cp "$ENV_FILE" "$preview_file"
  apply_final_policy_to_file "$preview_file"
  redact_env_file "$preview_file" "$FINAL_ENV_FILE"
}

verify_preconditions() {
  [[ -n "$PYTHON_BIN" ]] || blocked "precheck" "python unavailable"
  [[ -f "$ENV_FILE" ]] || blocked "precheck" "missing $ENV_FILE"
  [[ -n "$SEQUENCE_ARTIFACT_DIR" ]] || blocked "precheck" "missing SEQUENCE_ARTIFACT_DIR"
  [[ -d "$SEQUENCE_ARTIFACT_DIR" ]] || blocked "precheck" "missing sequence artifact dir: $SEQUENCE_ARTIFACT_DIR"
  [[ -f scripts/postgres_final_json_exit_audit.py ]] || blocked "precheck" "missing postgres_final_json_exit_audit.py"
}

run_final_audit() {
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

main() {
  write_plan
  if [[ ! -f "$ENV_FILE" ]]; then
    write_status "dry_run" "planned" "set CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY=run to execute; env file unavailable for preview"
    printf 'dry-run final JSON exit policy plan written to %s\n' "$PLAN_FILE"
    return 0
  fi

  write_sanitized_final_env_preview
  if [[ "$CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY" != "run" ]]; then
    write_status "dry_run" "planned" "set CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY=run to execute"
    printf 'dry-run final JSON exit policy plan written to %s\n' "$PLAN_FILE"
    return 0
  fi

  verify_preconditions
  local backup_file="$ARTIFACT_DIR/compose.env.before-final-json-exit.$RUN_ID.bak"
  cp "$ENV_FILE" "$backup_file"
  chmod 600 "$backup_file"
  redact_env_file "$backup_file" "$ARTIFACT_DIR/compose.env.before-final-json-exit.sanitized"
  write_status "running" "apply-final-policy" ""
  apply_final_policy_to_file "$ENV_FILE"
  redact_env_file "$ENV_FILE" "$ARTIFACT_DIR/compose.env.after-final-json-exit.sanitized"
  run_final_audit
  write_status "passed" "done" ""
}

main "$@"
