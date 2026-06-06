#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-miemie-pre}"
ENV_FILE="${ENV_FILE:-compose.env}"
COMPOSE_FILE_1="${COMPOSE_FILE_1:-docker-compose.yml}"
COMPOSE_FILE_2="${COMPOSE_FILE_2:-docker-compose.pre.override.yml}"
BACKUP_DIR="${BACKUP_DIR:-backend/backups/postgres}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"

if [ -f "$COMPOSE_FILE_2" ]; then
  docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE_1" -f "$COMPOSE_FILE_2" exec -T postgres \
    sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
    > "$BACKUP_DIR/miemie-postgres-$TIMESTAMP.sql"
else
  docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE_1" exec -T postgres \
    sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
    > "$BACKUP_DIR/miemie-postgres-$TIMESTAMP.sql"
fi

echo "$BACKUP_DIR/miemie-postgres-$TIMESTAMP.sql"
