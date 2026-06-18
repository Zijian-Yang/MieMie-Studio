#!/usr/bin/env bash
set -Eeuo pipefail

# Planned post-JSON-exit validation. The real run is gated by CONFIRM_POST_JSON_EXIT_VALIDATION=run.
python3 scripts/postgres_final_json_exit_audit.py --sequence-artifact-dir "$SEQUENCE_ARTIFACT_DIR" --env-file "compose.env" --artifact-dir "$ARTIFACT_DIR/final-json-exit-audit"
grep -q ready_for_post_json_exit_validation "$ARTIFACT_DIR/final-json-exit-audit/status.json"

export MIEMIE_DATABASE_ENABLED=true
export MIEMIE_DATABASE_WRITE_MODE=postgres
export MIEMIE_DATABASE_READ_MODE=postgres
export MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=
export MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=
export MIEMIE_DATABASE_READ_DOMAINS=
export MIEMIE_DATABASE_JSON_FALLBACK_READ=false
export MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false
export MIEMIE_DATABASE_RECONCILE_STRICT=true

docker compose --env-file "compose.env" -f docker-compose.yml -f "docker-compose.pre.override.yml" -p "miemie-pre" up -d api worker worker-video
curl -sS -D "$ARTIFACT_DIR/health-local.headers" -o "$ARTIFACT_DIR/health-local.json" "http://127.0.0.1:18100/api/health"
curl -sS -D "$ARTIFACT_DIR/health-public.headers" -o "$ARTIFACT_DIR/health-public.json" "https://pre-studio.miemie.co/api/health"
docker compose --env-file "compose.env" -f docker-compose.yml -f "docker-compose.pre.override.yml" -p "miemie-pre" ps
docker stats --no-stream
python3 scripts/postgres_reconcile_video_studio_tasks.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/video_studio_tasks_reconcile"
python3 scripts/postgres_reconcile_studio_tasks.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/studio_tasks_reconcile"
python3 scripts/postgres_reconcile_projects.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/projects_reconcile"
python3 scripts/postgres_reconcile_media_metadata.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/media_metadata_reconcile"
python3 scripts/postgres_reconcile_project_entities.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/project_entities_reconcile"
python3 scripts/postgres_reconcile_benchmark_records.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/benchmark_records_reconcile"
python3 scripts/postgres_reconcile_user_config.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/user_config_reconcile"
python3 scripts/postgres_reconcile_sessions.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/sessions_reconcile"
python3 scripts/postgres_reconcile_audio_studio.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/audio_studio_reconcile"
K6_VUS=30 K6_DURATION=90s K6_SLEEP_SECONDS=1 MIEMIE_BASE_URL="http://127.0.0.1:18100" LOADTEST_RUN_ID="$RUN_ID-post-json-exit-s1" k6 run loadtest/k6/s1-read.js --summary-export "$ARTIFACT_DIR/k6-s1-read.summary.json"
