#!/usr/bin/env bash
set -Eeuo pipefail

# Planned server-side final JSON exit sequence. The real run is gated by CONFIRM_SERVER_FINAL_EXIT_SEQUENCE=run.
CONFIRM_SERVER_SEQUENCE=run \
  RUN_ID="r84-server-final-exit-sequence-server-sequence" \
  ARTIFACT_DIR="docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r84-server-final-exit-sequence/server-sequence" \
  TMP_DIR="/tmp/r84-server-final-exit-sequence/server-sequence" \
  SERVER_SYNC="ff-only" \
  bash scripts/pre_studio_server_postgres_sequence.sh

SEQUENCE_ARTIFACT_DIR="docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r84-server-final-exit-sequence/server-sequence/sequence"

CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY=run \
  RUN_ID="r84-server-final-exit-sequence-apply-final-json-exit-policy" \
  ARTIFACT_DIR="docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r84-server-final-exit-sequence/apply-final-json-exit-policy" \
  TMP_DIR="/tmp/r84-server-final-exit-sequence/apply-final-json-exit-policy" \
  ENV_FILE="compose.env" \
  SEQUENCE_ARTIFACT_DIR="$SEQUENCE_ARTIFACT_DIR" \
  bash scripts/postgres_apply_final_json_exit_policy.sh

CONFIRM_POST_JSON_EXIT_VALIDATION=run \
  RUN_ID="r84-server-final-exit-sequence-post-json-exit-validation" \
  ARTIFACT_DIR="docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r84-server-final-exit-sequence/post-json-exit-validation" \
  TMP_DIR="/tmp/r84-server-final-exit-sequence/post-json-exit-validation" \
  ENV_FILE="compose.env" \
  SEQUENCE_ARTIFACT_DIR="$SEQUENCE_ARTIFACT_DIR" \
  bash scripts/postgres_post_json_exit_validation.sh

ROLLBACK_ENV_BACKUP_FILE="$(find "docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r84-server-final-exit-sequence/apply-final-json-exit-policy" -maxdepth 1 -name 'compose.env.before-final-json-exit.*.bak' -print | sort | tail -n 1)"
CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY=run \
  RUN_ID="r84-server-final-exit-sequence-rollback-final-json-exit-policy" \
  ARTIFACT_DIR="docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r84-server-final-exit-sequence/rollback-final-json-exit-policy" \
  TMP_DIR="/tmp/r84-server-final-exit-sequence/rollback-final-json-exit-policy" \
  ENV_FILE="compose.env" \
  ROLLBACK_ENV_BACKUP_FILE="$ROLLBACK_ENV_BACKUP_FILE" \
  bash scripts/postgres_rollback_final_json_exit_policy.sh
