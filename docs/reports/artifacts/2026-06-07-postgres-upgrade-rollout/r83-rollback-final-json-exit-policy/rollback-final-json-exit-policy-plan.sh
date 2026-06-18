#!/usr/bin/env bash
set -Eeuo pipefail

# Planned final JSON exit policy rollback. The real run is gated by CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY=run.
PRE_ROLLBACK_BACKUP_FILE="docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r83-rollback-final-json-exit-policy/compose.env.before-final-policy-rollback.r83-rollback-final-json-exit-policy-20260618.bak"
cp "$ENV_FILE" "$PRE_ROLLBACK_BACKUP_FILE"
cp "$ROLLBACK_ENV_BACKUP_FILE" "$ENV_FILE"
# writes compose.env.rollback-source.sanitized
# writes compose.env.before-rollback.sanitized
# writes compose.env.after-rollback.sanitized
docker compose --env-file "compose.env" -f docker-compose.yml -f "docker-compose.pre.override.yml" -p "miemie-pre" up -d api worker worker-video
curl -sS -D "$ARTIFACT_DIR/health-local.headers" -o "$ARTIFACT_DIR/health-local.json" "http://127.0.0.1:18100/api/health"
curl -sS -D "$ARTIFACT_DIR/health-public.headers" -o "$ARTIFACT_DIR/health-public.json" "https://pre-studio.miemie.co/api/health"
docker compose --env-file "compose.env" -f docker-compose.yml -f "docker-compose.pre.override.yml" -p "miemie-pre" ps
