#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-postgres-backup-retention-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r116-postgres-backup-retention}"
BACKUP_DIR="${BACKUP_DIR:-backend/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
MIN_KEEP="${MIN_KEEP:-3}"
CONFIRM_POSTGRES_BACKUP_RETENTION="${CONFIRM_POSTGRES_BACKUP_RETENTION:-dry-run}"

mkdir -p "$ARTIFACT_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
MANIFEST_FILE="$ARTIFACT_DIR/postgres-backup-retention-manifest.tsv"

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

"$PYTHON_BIN" - "$BACKUP_DIR" "$RETENTION_DAYS" "$MIN_KEEP" "$CONFIRM_POSTGRES_BACKUP_RETENTION" "$STATUS_FILE" "$MANIFEST_FILE" "$RUN_ID" <<'PY'
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

backup_dir = Path(sys.argv[1])
retention_days = int(sys.argv[2])
min_keep = int(sys.argv[3])
confirm = sys.argv[4]
status_file = Path(sys.argv[5])
manifest_file = Path(sys.argv[6])
run_id = sys.argv[7]

now = time.time()
backup_dir.mkdir(parents=True, exist_ok=True)
backups = sorted(
    backup_dir.glob("miemie-postgres-*.sql"),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
)

rows: list[dict] = []
for index, path in enumerate(backups):
    stat = path.stat()
    age_days = (now - stat.st_mtime) / 86400
    keep_reason = ""
    action = "keep"
    if index < min_keep:
        keep_reason = "min_keep"
    elif age_days <= retention_days:
        keep_reason = "within_retention"
    else:
        keep_reason = "expired"
        action = "delete_candidate"
    rows.append(
        {
            "path": str(path),
            "size_bytes": stat.st_size,
            "mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)),
            "age_days": age_days,
            "action": action,
            "reason": keep_reason,
        }
    )

deleted: list[str] = []
if confirm == "prune":
    for row in rows:
        if row["action"] != "delete_candidate":
            continue
        Path(row["path"]).unlink()
        deleted.append(row["path"])
        row["action"] = "deleted"

manifest_file.parent.mkdir(parents=True, exist_ok=True)
with manifest_file.open("w", encoding="utf-8") as handle:
    handle.write("path\tsize_bytes\tmtime\tage_days\taction\treason\n")
    for row in rows:
        handle.write(
            f"{row['path']}\t{row['size_bytes']}\t{row['mtime']}\t{row['age_days']:.6f}\t{row['action']}\t{row['reason']}\n"
        )

delete_candidates = [row["path"] for row in rows if row["action"] == "delete_candidate"]
state = "passed" if confirm == "prune" else "dry_run"
stage = "done" if confirm == "prune" else "planned"
reason = (
    f"deleted {len(deleted)} expired backups"
    if confirm == "prune"
    else "set CONFIRM_POSTGRES_BACKUP_RETENTION=prune to delete expired backups"
)
status = {
    "run_id": run_id,
    "state": state,
    "stage": stage,
    "reason": reason,
    "backup_dir": str(backup_dir),
    "retention_days": retention_days,
    "min_keep": min_keep,
    "total_backups": len(rows),
    "delete_candidate_count": len(delete_candidates),
    "deleted_count": len(deleted),
    "manifest": str(manifest_file),
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
status_file.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(json.dumps(status, ensure_ascii=False, indent=2))
PY
