#!/usr/bin/env bash
set -euo pipefail

DUMP_FILE="${1:-}"
PROJECT_NAME="${PROJECT_NAME:-miemie-pre}"
ENV_FILE="${ENV_FILE:-compose.env}"
COMPOSE_FILE_1="${COMPOSE_FILE_1:-docker-compose.yml}"
# An explicitly empty COMPOSE_FILE_2 disables the legacy second Compose file.
COMPOSE_FILE_2="${COMPOSE_FILE_2-docker-compose.pre.override.yml}"
RESTORE_DB="${RESTORE_DB:-miemie_restore_check}"

if [ -z "$DUMP_FILE" ] || [ ! -s "$DUMP_FILE" ]; then
  echo "usage: $0 path/to/postgres-dump.sql" >&2
  exit 2
fi

compose_cmd=(docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE_1")
if [ -f "$COMPOSE_FILE_2" ]; then
  compose_cmd+=(-f "$COMPOSE_FILE_2")
fi

cleanup_restore_database() {
  "${compose_cmd[@]}" exec -T postgres sh -lc \
    'dropdb -U "$POSTGRES_USER" --if-exists "$0"' \
    "$RESTORE_DB" >/dev/null 2>&1 || true
}

trap cleanup_restore_database EXIT

"${compose_cmd[@]}" exec -T postgres sh -lc \
  'dropdb -U "$POSTGRES_USER" --if-exists "$0" && createdb -U "$POSTGRES_USER" "$0"' \
  "$RESTORE_DB"

if [ "$(LC_ALL=C od -An -N5 -c "$DUMP_FILE" | tr -d ' \n')" = "PGDMP" ]; then
  "${compose_cmd[@]}" exec -T postgres sh -lc \
    'pg_restore --exit-on-error --no-owner --no-privileges -U "$POSTGRES_USER" -d "$0"' \
    "$RESTORE_DB" < "$DUMP_FILE"
else
  "${compose_cmd[@]}" exec -T postgres sh -lc \
    'psql -U "$POSTGRES_USER" -d "$0" -v ON_ERROR_STOP=1' \
    "$RESTORE_DB" < "$DUMP_FILE"
fi

"${compose_cmd[@]}" exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$0" -tAc "select 1"' \
  "$RESTORE_DB"

cleanup_restore_database
trap - EXIT

echo "restore rehearsal ok: $RESTORE_DB"
