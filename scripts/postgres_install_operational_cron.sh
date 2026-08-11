#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-postgres-operational-cron-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r116-postgres-operational-cron}"
CONFIRM_POSTGRES_OPERATIONAL_CRON="${CONFIRM_POSTGRES_OPERATIONAL_CRON:-dry-run}"
CRON_FILE="${CRON_FILE:-/etc/cron.d/miemie-postgres-ops}"
INSTALL_ROOT="${INSTALL_ROOT:-/opt/miemie-pre}"
CRON_USER="${CRON_USER:-root}"
ALERT_ENV_FILE="${ALERT_ENV_FILE:-/etc/miemie-postgres-ops-alert.env}"
OPS_SCHEDULE="${OPS_SCHEDULE:-15 3 * * *}"
RETENTION_SCHEDULE="${RETENTION_SCHEDULE:-45 3 * * *}"
SNAPSHOT_SCHEDULE="${SNAPSHOT_SCHEDULE:-15 5 * * *}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
MIN_KEEP="${MIN_KEEP:-3}"

mkdir -p "$ARTIFACT_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
CRON_PREVIEW_FILE="$ARTIFACT_DIR/miemie-postgres-ops.cron"

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
  local reason="$3"
  cat > "$STATUS_FILE" <<JSON
{
  "run_id": "$(json_escape "$RUN_ID")",
  "state": "$(json_escape "$state")",
  "stage": "$(json_escape "$stage")",
  "reason": "$(json_escape "$reason")",
  "cron_file": "$(json_escape "$CRON_FILE")",
  "install_root": "$(json_escape "$INSTALL_ROOT")",
  "cron_preview": "$(json_escape "$CRON_PREVIEW_FILE")",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
}

write_cron_preview() {
  cat > "$CRON_PREVIEW_FILE" <<CRON
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# MieMie PostgreSQL-only operational readiness.
# Runs a fresh backup plus restore rehearsal. Outputs stay on the server.
$OPS_SCHEDULE $CRON_USER cd "$INSTALL_ROOT" || exit 1; mkdir -p logs validation-artifacts || exit 1; if [ -f "$ALERT_ENV_FILE" ]; then set -a; . "$ALERT_ENV_FILE"; set +a; fi; RUN_STAMP=\$(date +\\%Y\\%m\\%d-\\%H\\%M\\%S); POSTGRES_OPS_TRIGGER=cron RUN_ID=postgres-ops-\$RUN_STAMP ARTIFACT_DIR=validation-artifacts/postgres-ops-\$RUN_STAMP CONFIRM_POSTGRES_OPERATIONAL_READINESS=run POSTGRES_OPS_BACKUP_RESTORE=run bash scripts/postgres_operational_readiness.sh >> logs/postgres-operational-readiness-cron.log 2>&1

# Prunes old PostgreSQL dumps after the readiness gate creates a fresh one.
$RETENTION_SCHEDULE $CRON_USER cd "$INSTALL_ROOT" || exit 1; mkdir -p logs validation-artifacts || exit 1; if [ -f "$ALERT_ENV_FILE" ]; then set -a; . "$ALERT_ENV_FILE"; set +a; fi; RUN_STAMP=\$(date +\\%Y\\%m\\%d-\\%H\\%M\\%S); POSTGRES_OPS_TRIGGER=cron RUN_ID=postgres-backup-retention-\$RUN_STAMP ARTIFACT_DIR=validation-artifacts/postgres-backup-retention-\$RUN_STAMP RETENTION_DAYS=$RETENTION_DAYS MIN_KEEP=$MIN_KEEP CONFIRM_POSTGRES_BACKUP_RETENTION=prune bash scripts/postgres_backup_retention.sh >> logs/postgres-backup-retention-cron.log 2>&1

# Captures read-only PostgreSQL database operational metadata.
$SNAPSHOT_SCHEDULE $CRON_USER cd "$INSTALL_ROOT" || exit 1; mkdir -p logs validation-artifacts || exit 1; if [ -f "$ALERT_ENV_FILE" ]; then set -a; . "$ALERT_ENV_FILE"; set +a; fi; RUN_STAMP=\$(date +\\%Y\\%m\\%d-\\%H\\%M\\%S); POSTGRES_OPS_TRIGGER=cron RUN_ID=postgres-database-snapshot-\$RUN_STAMP ARTIFACT_DIR=validation-artifacts/postgres-database-snapshot-\$RUN_STAMP CONFIRM_POSTGRES_DATABASE_SNAPSHOT=run bash scripts/postgres_database_snapshot.sh >> logs/postgres-database-snapshot-cron.log 2>&1
CRON
}

write_cron_preview

if [[ "$CONFIRM_POSTGRES_OPERATIONAL_CRON" != "install" ]]; then
  write_status "dry_run" "planned" "set CONFIRM_POSTGRES_OPERATIONAL_CRON=install to write cron file"
  printf 'dry-run cron preview written to %s\n' "$CRON_PREVIEW_FILE"
  exit 0
fi

if [[ "$(id -u)" != "0" ]]; then
  write_status "blocked" "precheck" "cron install requires root"
  echo "cron install requires root" >&2
  exit 2
fi

install -m 0644 "$CRON_PREVIEW_FILE" "$CRON_FILE"
write_status "passed" "done" "installed cron file"
printf 'installed %s\n' "$CRON_FILE"
