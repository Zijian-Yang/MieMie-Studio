#!/usr/bin/env bash
set -Eeuo pipefail

# Planned final JSON exit policy application. The real run is gated by CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY=run.
BACKUP_FILE="docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r82-apply-final-json-exit-policy/compose.env.before-final-json-exit.r82-apply-final-json-exit-policy-20260618.bak"
cp "$ENV_FILE" "$BACKUP_FILE"
MIEMIE_DATABASE_ENABLED=true
MIEMIE_DATABASE_WRITE_MODE=postgres
MIEMIE_DATABASE_READ_MODE=postgres
MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=
MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=
MIEMIE_DATABASE_READ_DOMAINS=
MIEMIE_DATABASE_JSON_FALLBACK_READ=false
MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false
MIEMIE_DATABASE_RECONCILE_STRICT=true
python3 scripts/postgres_final_json_exit_audit.py --sequence-artifact-dir "$SEQUENCE_ARTIFACT_DIR" --env-file "$ENV_FILE" --artifact-dir "$ARTIFACT_DIR/final-json-exit-audit"
grep -q ready_for_post_json_exit_validation "$ARTIFACT_DIR/final-json-exit-audit/status.json"
