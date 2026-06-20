#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-postgres-operational-cron-evidence-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r119-postgres-operational-cron-evidence}"
CONFIRM_POSTGRES_CRON_EVIDENCE="${CONFIRM_POSTGRES_CRON_EVIDENCE:-dry-run}"
VALIDATION_ROOT="${VALIDATION_ROOT:-validation-artifacts}"
CRON_FILE="${CRON_FILE:-/etc/cron.d/miemie-postgres-ops}"
OPS_PREFIX="${OPS_PREFIX:-postgres-ops-}"
RETENTION_PREFIX="${RETENTION_PREFIX:-postgres-backup-retention-}"
CRON_EVIDENCE_NOT_BEFORE="${CRON_EVIDENCE_NOT_BEFORE:-}"
CRON_EVIDENCE_STRICT_WAIT="${CRON_EVIDENCE_STRICT_WAIT:-false}"
CRON_SERVICE_STATE_OVERRIDE="${CRON_SERVICE_STATE_OVERRIDE:-}"

mkdir -p "$ARTIFACT_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
SUMMARY_FILE="$ARTIFACT_DIR/cron-evidence-summary.tsv"
PLAN_FILE="$ARTIFACT_DIR/postgres-operational-cron-evidence-plan.sh"
CRON_SNAPSHOT="$ARTIFACT_DIR/miemie-postgres-ops.cron"
CRON_SERVICE_STATUS="$ARTIFACT_DIR/cron-service-status.txt"

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

write_plan() {
  cat > "$PLAN_FILE" <<PLAN
#!/usr/bin/env bash
set -Eeuo pipefail

# Check the latest scheduled PostgreSQL operational cron evidence.
# Default mode only writes this plan. Execute the current check with:
# CONFIRM_POSTGRES_CRON_EVIDENCE=check bash scripts/postgres_operational_cron_evidence.sh
#
# Evidence roots:
# - operational readiness artifacts: $VALIDATION_ROOT/${OPS_PREFIX}*
# - backup retention artifacts: $VALIDATION_ROOT/${RETENTION_PREFIX}*
#
# A state of "waiting" means no scheduled cron artifact is available yet.
# Set CRON_EVIDENCE_STRICT_WAIT=true when a CI/deploy gate should fail on waiting.
PLAN
}

write_dry_run_status() {
  "$PYTHON_BIN" - "$STATUS_FILE" "$RUN_ID" "$ARTIFACT_DIR" <<'PY'
import json
import sys
import time
from pathlib import Path

status_file = Path(sys.argv[1])
payload = {
    "run_id": sys.argv[2],
    "state": "dry_run",
    "stage": "planned",
    "reason": "set CONFIRM_POSTGRES_CRON_EVIDENCE=check to inspect scheduled cron artifacts",
    "artifact_dir": sys.argv[3],
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
status_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

write_cron_snapshots() {
  if [[ -f "$CRON_FILE" ]]; then
    cp "$CRON_FILE" "$CRON_SNAPSHOT"
  else
    printf 'missing: %s\n' "$CRON_FILE" > "$CRON_SNAPSHOT"
  fi

  if [[ -n "$CRON_SERVICE_STATE_OVERRIDE" ]]; then
    printf '%s\n' "$CRON_SERVICE_STATE_OVERRIDE" > "$CRON_SERVICE_STATUS"
  elif command -v systemctl >/dev/null 2>&1; then
    systemctl is-active cron > "$CRON_SERVICE_STATUS" 2>/dev/null \
      || systemctl is-active crond > "$CRON_SERVICE_STATUS" 2>/dev/null \
      || printf 'unknown\n' > "$CRON_SERVICE_STATUS"
  else
    printf 'unknown\n' > "$CRON_SERVICE_STATUS"
  fi
}

run_check() {
  write_cron_snapshots
  "$PYTHON_BIN" - \
    "$STATUS_FILE" \
    "$SUMMARY_FILE" \
    "$RUN_ID" \
    "$ARTIFACT_DIR" \
    "$VALIDATION_ROOT" \
    "$OPS_PREFIX" \
    "$RETENTION_PREFIX" \
    "$CRON_FILE" \
    "$CRON_SERVICE_STATUS" \
    "$CRON_EVIDENCE_NOT_BEFORE" \
    "$CRON_EVIDENCE_STRICT_WAIT" <<'PY'
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


status_file = Path(sys.argv[1])
summary_file = Path(sys.argv[2])
run_id = sys.argv[3]
artifact_dir = Path(sys.argv[4])
validation_root = Path(sys.argv[5])
ops_prefix = sys.argv[6]
retention_prefix = sys.argv[7]
cron_file = Path(sys.argv[8])
cron_service_status_file = Path(sys.argv[9])
not_before_raw = sys.argv[10]
strict_wait = sys.argv[11].lower() == "true"


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except ValueError:
        return None


def read_status(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {
            "state": "invalid",
            "stage": "invalid",
            "reason": f"invalid status json: {exc}",
            "updated_at": "",
        }


def latest_status(prefix: str) -> tuple[Path | None, dict[str, Any] | None]:
    if not validation_root.exists():
        return None, None
    candidates = sorted(
        validation_root.glob(f"{prefix}*/status.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    not_before = parse_time(not_before_raw)
    for candidate in candidates:
        status = read_status(candidate)
        updated = parse_time(str(status.get("updated_at", "")))
        if not_before is not None and updated is not None and updated < not_before:
            continue
        return candidate, status
    return None, None


def service_state() -> str:
    if not cron_service_status_file.exists():
        return "unknown"
    return cron_service_status_file.read_text(encoding="utf-8").strip() or "unknown"


ops_path, ops_status = latest_status(ops_prefix)
retention_path, retention_status = latest_status(retention_prefix)
cron_state = service_state()

rows: list[tuple[str, str, str, str]] = []
rows.append(("cron_file", "present" if cron_file.exists() else "missing", str(cron_file), ""))
rows.append(("cron_service", cron_state, str(cron_service_status_file), ""))

def append_status(label: str, path: Path | None, status: dict[str, Any] | None) -> None:
    if path is None or status is None:
        rows.append((label, "missing", "", "no scheduled artifact found"))
        return
    rows.append((label, str(status.get("state", "")), str(path), str(status.get("reason", ""))))


append_status("operational_readiness", ops_path, ops_status)
append_status("backup_retention", retention_path, retention_status)

summary_file.write_text(
    "check\tstate\tpath\tdetail\n"
    + "".join(
        f"{check or '-'}\t{state or '-'}\t{path or '-'}\t{detail or '-'}\n"
        for check, state, path, detail in rows
    ),
    encoding="utf-8",
)

reasons: list[str] = []
state = "passed"

if not cron_file.exists():
    state = "blocked"
    reasons.append("cron file missing")
if cron_state not in {"active", "unknown"}:
    state = "blocked"
    reasons.append(f"cron service is {cron_state}")

if ops_status is None:
    if state != "blocked":
        state = "waiting"
    reasons.append("no operational readiness cron artifact yet")
elif ops_status.get("state") not in {"passed", "passed_with_warnings"}:
    state = "blocked"
    reasons.append(f"operational readiness state is {ops_status.get('state')}")

if retention_status is None:
    if state != "blocked":
        state = "waiting"
    reasons.append("no backup retention cron artifact yet")
elif retention_status.get("state") != "passed":
    state = "blocked"
    reasons.append(f"backup retention state is {retention_status.get('state')}")

if state == "waiting" and strict_wait:
    state = "blocked"
    reasons.append("strict wait enabled")

payload = {
    "run_id": run_id,
    "state": state,
    "stage": "done",
    "reason": "; ".join(reasons),
    "artifact_dir": str(artifact_dir),
    "validation_root": str(validation_root),
    "cron_file": str(cron_file),
    "cron_service_state": cron_state,
    "operational_readiness": {
        "status_path": str(ops_path) if ops_path else "",
        "state": ops_status.get("state") if ops_status else "",
        "updated_at": ops_status.get("updated_at") if ops_status else "",
    },
    "backup_retention": {
        "status_path": str(retention_path) if retention_path else "",
        "state": retention_status.get("state") if retention_status else "",
        "updated_at": retention_status.get("updated_at") if retention_status else "",
    },
    "not_before": not_before_raw,
    "strict_wait": strict_wait,
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
status_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
raise SystemExit(2 if state == "blocked" else 0)
PY
}

write_plan

if [[ "$CONFIRM_POSTGRES_CRON_EVIDENCE" != "check" ]]; then
  write_dry_run_status
  printf 'dry-run cron evidence plan written to %s\n' "$PLAN_FILE"
  exit 0
fi

run_check
