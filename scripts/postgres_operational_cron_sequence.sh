#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-postgres-operational-cron-sequence-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r122-postgres-operational-cron-sequence}"
CONFIRM_POSTGRES_CRON_SEQUENCE="${CONFIRM_POSTGRES_CRON_SEQUENCE:-dry-run}"
VALIDATION_ROOT="${VALIDATION_ROOT:-validation-artifacts}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
MIN_KEEP="${MIN_KEEP:-3}"
ALERT_ENV_FILE="${ALERT_ENV_FILE:-/etc/miemie-postgres-ops-alert.env}"

mkdir -p "$ARTIFACT_DIR" "$VALIDATION_ROOT"

STATUS_FILE="$ARTIFACT_DIR/status.json"
PLAN_FILE="$ARTIFACT_DIR/postgres-operational-cron-sequence-plan.sh"
SUMMARY_FILE="$ARTIFACT_DIR/postgres-operational-cron-sequence-summary.tsv"

if [[ -x "backend/.venv/bin/python" ]]; then
  PYTHON_BIN="backend/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "python3 missing" >&2
  exit 2
fi

write_status() {
  local state="$1"
  local stage="$2"
  local reason="${3:-}"
  "$PYTHON_BIN" - \
    "$STATUS_FILE" \
    "$RUN_ID" \
    "$state" \
    "$stage" \
    "$reason" \
    "$ARTIFACT_DIR" \
    "$CONFIRM_POSTGRES_CRON_SEQUENCE" \
    "$VALIDATION_ROOT" <<'PY'
import json
import sys
import time
from pathlib import Path

status_file = Path(sys.argv[1])
payload = {
    "run_id": sys.argv[2],
    "state": sys.argv[3],
    "stage": sys.argv[4],
    "reason": sys.argv[5],
    "artifact_dir": sys.argv[6],
    "confirm": sys.argv[7],
    "validation_root": sys.argv[8],
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
status_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

write_plan() {
  cat > "$PLAN_FILE" <<PLAN
#!/usr/bin/env bash
set -Eeuo pipefail

# PostgreSQL operational cron sequence gate.
# Default mode is dry-run. Execute the cron-equivalent sequence with:
# CONFIRM_POSTGRES_CRON_SEQUENCE=run bash scripts/postgres_operational_cron_sequence.sh
#
# Sequence:
# 1. Run operational readiness with fresh backup and restore rehearsal.
# 2. Run backup retention prune with RETENTION_DAYS=${RETENTION_DAYS} and MIN_KEEP=${MIN_KEEP}.
# 3. Run read-only database snapshot.
# 4. Run cron evidence gate with CRON_EVIDENCE_STRICT_WAIT=true and CRON_EVIDENCE_NOT_BEFORE
#    set to the sequence start time, so only fresh artifacts from this sequence pass.
#    Sequence artifacts use POSTGRES_OPS_TRIGGER=manual_sequence and the evidence gate
#    requires CRON_EVIDENCE_REQUIRED_TRIGGER=manual_sequence.
#
# Optional local alert env:
# - If ALERT_ENV_FILE exists during run mode, it is sourced before subcommands.
# - The env file path is recorded, but its contents are never copied into artifacts.
PLAN
}

write_dry_run() {
  printf 'step\tstate\trun_id\tartifact_dir\texit_code\n' > "$SUMMARY_FILE"
  write_status "dry_run" "planned" "set CONFIRM_POSTGRES_CRON_SEQUENCE=run to execute cron-equivalent PostgreSQL operational sequence"
  printf 'dry-run cron sequence plan written to %s\n' "$PLAN_FILE"
}

append_summary() {
  local step="$1"
  local state="$2"
  local step_run_id="$3"
  local step_artifact="$4"
  local exit_code="$5"
  printf '%s\t%s\t%s\t%s\t%s\n' "$step" "$state" "$step_run_id" "$step_artifact" "$exit_code" >> "$SUMMARY_FILE"
}

run_step() {
  local step="$1"
  local step_run_id="$2"
  local step_artifact="$3"
  shift 3

  set +e
  "$@"
  local exit_code=$?
  set -e

  if [[ "$exit_code" -eq 0 ]]; then
    append_summary "$step" "passed" "$step_run_id" "$step_artifact" "$exit_code"
    return 0
  fi

  append_summary "$step" "blocked" "$step_run_id" "$step_artifact" "$exit_code"
  write_status "blocked" "$step" "$step failed with exit code $exit_code"
  return "$exit_code"
}

verify_evidence_passed() {
  local evidence_status="$1"
  "$PYTHON_BIN" - "$evidence_status" <<'PY'
import json
import sys
from pathlib import Path

status = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if status.get("state") != "passed":
    raise SystemExit(f"cron evidence state is {status.get('state')}: {status.get('reason')}")
PY
}

run_sequence() {
  local sequence_stamp
  local sequence_not_before
  sequence_stamp="$(date +%Y%m%d-%H%M%S)"
  sequence_not_before="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  printf 'step\tstate\trun_id\tartifact_dir\texit_code\n' > "$SUMMARY_FILE"
  write_status "running" "started" "sequence started at $sequence_not_before"

  if [[ -f "$ALERT_ENV_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$ALERT_ENV_FILE"
  fi

  local ops_run_id="postgres-ops-${sequence_stamp}"
  local retention_run_id="postgres-backup-retention-${sequence_stamp}"
  local snapshot_run_id="postgres-database-snapshot-${sequence_stamp}"
  local evidence_run_id="postgres-operational-cron-sequence-evidence-${sequence_stamp}"

  local ops_artifact="$VALIDATION_ROOT/$ops_run_id"
  local retention_artifact="$VALIDATION_ROOT/$retention_run_id"
  local snapshot_artifact="$VALIDATION_ROOT/$snapshot_run_id"
  local evidence_artifact="$ARTIFACT_DIR/evidence"

  run_step "operational_readiness" "$ops_run_id" "$ops_artifact" \
    env RUN_ID="$ops_run_id" \
      ARTIFACT_DIR="$ops_artifact" \
      POSTGRES_OPS_TRIGGER=manual_sequence \
      CONFIRM_POSTGRES_OPERATIONAL_READINESS=run \
      POSTGRES_OPS_BACKUP_RESTORE=run \
      bash scripts/postgres_operational_readiness.sh

  run_step "backup_retention" "$retention_run_id" "$retention_artifact" \
    env RUN_ID="$retention_run_id" \
      ARTIFACT_DIR="$retention_artifact" \
      POSTGRES_OPS_TRIGGER=manual_sequence \
      RETENTION_DAYS="$RETENTION_DAYS" \
      MIN_KEEP="$MIN_KEEP" \
      CONFIRM_POSTGRES_BACKUP_RETENTION=prune \
      bash scripts/postgres_backup_retention.sh

  run_step "database_snapshot" "$snapshot_run_id" "$snapshot_artifact" \
    env RUN_ID="$snapshot_run_id" \
      ARTIFACT_DIR="$snapshot_artifact" \
      POSTGRES_OPS_TRIGGER=manual_sequence \
      CONFIRM_POSTGRES_DATABASE_SNAPSHOT=run \
      bash scripts/postgres_database_snapshot.sh

  run_step "cron_evidence" "$evidence_run_id" "$evidence_artifact" \
    env RUN_ID="$evidence_run_id" \
      ARTIFACT_DIR="$evidence_artifact" \
      VALIDATION_ROOT="$VALIDATION_ROOT" \
      CRON_EVIDENCE_NOT_BEFORE="$sequence_not_before" \
      CRON_EVIDENCE_REQUIRED_TRIGGER=manual_sequence \
      CRON_EVIDENCE_STRICT_WAIT=true \
      CONFIRM_POSTGRES_CRON_EVIDENCE=check \
      bash scripts/postgres_operational_cron_evidence.sh

  verify_evidence_passed "$evidence_artifact/status.json"
  write_status "passed" "done" "cron-equivalent PostgreSQL operational sequence passed"
}

write_plan

if [[ "$CONFIRM_POSTGRES_CRON_SEQUENCE" != "run" ]]; then
  write_dry_run
  exit 0
fi

run_sequence
