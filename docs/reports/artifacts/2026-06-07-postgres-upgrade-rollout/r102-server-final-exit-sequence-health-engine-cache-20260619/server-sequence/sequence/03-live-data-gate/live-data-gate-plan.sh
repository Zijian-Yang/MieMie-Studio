#!/usr/bin/env bash
set -Eeuo pipefail

# Planned server-side staging data gate. This plan is intentionally redacted.
export MIEMIE_DATABASE_URL='<from compose.env redacted>'
export MIEMIE_DATABASE_ENABLED=true
export MIEMIE_DATABASE_WRITE_MODE=file
export MIEMIE_DATABASE_READ_MODE=file
export MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=
export MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=
export MIEMIE_DATABASE_READ_DOMAINS=
export MIEMIE_DATABASE_JSON_FALLBACK_READ=true
export MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=false
export MIEMIE_DATABASE_RECONCILE_STRICT=true

# alembic-upgrade-head: alembic upgrade head
$PYTHON_BIN -m alembic -c backend/alembic.ini upgrade head

# per-domain JSON -> PostgreSQL backfill and reconcile
backend/.venv/bin/python scripts/postgres_backfill_video_studio_tasks.py --data-root "backend/data" --output "$ARTIFACT_DIR/video_studio_tasks_backfill.json"
backend/.venv/bin/python scripts/postgres_reconcile_video_studio_tasks.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/video_studio_tasks_reconcile"
backend/.venv/bin/python scripts/postgres_backfill_studio_tasks.py --data-root "backend/data" --output "$ARTIFACT_DIR/studio_tasks_backfill.json"
backend/.venv/bin/python scripts/postgres_reconcile_studio_tasks.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/studio_tasks_reconcile"
backend/.venv/bin/python scripts/postgres_backfill_projects.py --data-root "backend/data" --output "$ARTIFACT_DIR/projects_backfill.json"
backend/.venv/bin/python scripts/postgres_reconcile_projects.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/projects_reconcile"
backend/.venv/bin/python scripts/postgres_backfill_media_metadata.py --data-root "backend/data" --output "$ARTIFACT_DIR/media_metadata_backfill.json"
backend/.venv/bin/python scripts/postgres_reconcile_media_metadata.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/media_metadata_reconcile"
backend/.venv/bin/python scripts/postgres_backfill_project_entities.py --data-root "backend/data" --output "$ARTIFACT_DIR/project_entities_backfill.json"
backend/.venv/bin/python scripts/postgres_reconcile_project_entities.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/project_entities_reconcile"
backend/.venv/bin/python scripts/postgres_backfill_benchmark_records.py --data-root "backend/data" --output "$ARTIFACT_DIR/benchmark_records_backfill.json"
backend/.venv/bin/python scripts/postgres_reconcile_benchmark_records.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/benchmark_records_reconcile"
backend/.venv/bin/python scripts/postgres_backfill_user_config.py --data-root "backend/data" --output "$ARTIFACT_DIR/user_config_backfill.json"
backend/.venv/bin/python scripts/postgres_reconcile_user_config.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/user_config_reconcile"
backend/.venv/bin/python scripts/postgres_backfill_sessions.py --data-root "backend/data" --output "$ARTIFACT_DIR/sessions_backfill.json"
backend/.venv/bin/python scripts/postgres_reconcile_sessions.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/sessions_reconcile"
backend/.venv/bin/python scripts/postgres_backfill_audio_studio.py --data-root "backend/data" --output "$ARTIFACT_DIR/audio_studio_backfill.json"
backend/.venv/bin/python scripts/postgres_reconcile_audio_studio.py --data-root "backend/data" --output-dir "$ARTIFACT_DIR/audio_studio_reconcile"

BACKUP_DIR="$TMP_DIR/postgres-backups" bash scripts/postgres_backup.sh
bash scripts/postgres_restore_rehearsal.sh "$BACKUP_SQL"
