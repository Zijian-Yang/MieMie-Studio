#!/usr/bin/env bash

MIEMIE_CONFIG_FILE="${MIEMIE_CONFIG_FILE:-/etc/miemie/miemie.conf}"

miemie_load_config() {
  [[ -f "$MIEMIE_CONFIG_FILE" ]] || { echo "miemie config missing: $MIEMIE_CONFIG_FILE" >&2; return 2; }
  # shellcheck disable=SC1090
  source "$MIEMIE_CONFIG_FILE"
  : "${MIEMIE_INSTALL_ROOT:?}"
  : "${MIEMIE_PROJECT_NAME:?}"
  : "${MIEMIE_ENV_FILE:?}"
  : "${MIEMIE_RELEASE_STATE_DIR:?}"
  MIEMIE_COMPOSE_FILE="$MIEMIE_INSTALL_ROOT/docker-compose.yml"
}

miemie_require_root() {
  if [[ "${MIEMIE_ALLOW_NON_ROOT:-false}" != "true" && "$(id -u)" != "0" ]]; then
    echo "this command requires root" >&2
    return 2
  fi
}

miemie_compose() {
  docker compose -p "$MIEMIE_PROJECT_NAME" --env-file "$MIEMIE_ENV_FILE" -f "$MIEMIE_COMPOSE_FILE" "$@"
}

miemie_env_value() {
  local key="$1"
  sed -n "s/^${key}=//p" "$MIEMIE_ENV_FILE" | tail -n 1
}

miemie_set_env() {
  local key="$1" value="$2" temp
  temp="${MIEMIE_ENV_FILE}.tmp.$$"
  awk -v key="$key" -v value="$value" '
    BEGIN { replaced=0 }
    index($0, key "=")==1 { print key "=" value; replaced=1; next }
    { print }
    END { if (!replaced) print key "=" value }
  ' "$MIEMIE_ENV_FILE" > "$temp"
  chmod 600 "$temp"
  mv "$temp" "$MIEMIE_ENV_FILE"
}

miemie_host_port() {
  local port
  port="$(miemie_env_value MIEMIE_HOST_PORT)"
  printf '%s' "${port:-8000}"
}

miemie_lock() {
  mkdir -p "$MIEMIE_RELEASE_STATE_DIR"
  exec 9>"$MIEMIE_RELEASE_STATE_DIR/operator.lock"
  flock -n 9 || { echo "another miemie operation is running" >&2; return 3; }
}

miemie_validate_service() {
  case "$1" in api|worker|worker-video|worker-ops|scheduler|postgres|redis|migrate) return 0 ;; *) return 1 ;; esac
}

miemie_secure_password() {
  local prompt="${1:-Administrator password}"
  if [[ -n "${MIEMIE_ADMIN_PASSWORD:-}" ]]; then return 0; fi
  read -r -s -p "$prompt: " MIEMIE_ADMIN_PASSWORD; printf '\n'
  read -r -s -p "Confirm password: " confirmation; printf '\n'
  [[ "$MIEMIE_ADMIN_PASSWORD" == "$confirmation" ]] || { unset MIEMIE_ADMIN_PASSWORD confirmation; echo "password confirmation mismatch" >&2; return 2; }
  export MIEMIE_ADMIN_PASSWORD
  unset confirmation
}

miemie_current_commit() {
  if [[ -f "$MIEMIE_RELEASE_STATE_DIR/current.env" ]]; then
    sed -n 's/^commit=//p' "$MIEMIE_RELEASE_STATE_DIR/current.env" | tail -n 1
  else
    git -C "$MIEMIE_INSTALL_ROOT" rev-parse HEAD
  fi
}

miemie_current_image() {
  if [[ -f "$MIEMIE_RELEASE_STATE_DIR/current.env" ]]; then
    sed -n 's/^image=//p' "$MIEMIE_RELEASE_STATE_DIR/current.env" | tail -n 1
  else
    miemie_env_value MIEMIE_IMAGE
  fi
}

miemie_state_value() {
  local key="$1" file="${2:-$MIEMIE_RELEASE_STATE_DIR/current.env}"
  [[ -f "$file" ]] || return 0
  sed -n "s/^${key}=//p" "$file" | tail -n 1
}

miemie_wait_health() {
  local attempts="${1:-60}" port
  port="$(miemie_host_port)"
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS --connect-timeout 3 --max-time 5 "http://127.0.0.1:$port/api/health" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

miemie_workers_healthy() {
  local service
  for service in worker worker-video worker-ops scheduler; do
    [[ -n "$(miemie_compose ps --status running -q "$service")" ]] || return 1
  done
}

miemie_migration_head() {
  miemie_compose exec -T postgres sh -lc \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select version_num from alembic_version limit 1"' \
    2>/dev/null | tr -d '[:space:]' || true
}

miemie_write_release_manifest() {
  local file="$1" commit="$2" image="$3" previous_commit="$4" previous_image="$5"
  local backup_id="$6" backup_path="$7" state="$8" migration_head="${9:-}" temp
  mkdir -p "$MIEMIE_RELEASE_STATE_DIR"
  chmod 700 "$MIEMIE_RELEASE_STATE_DIR"
  temp="${file}.tmp.$$"
  cat > "$temp" <<EOF
commit=$commit
image=$image
previous_commit=$previous_commit
previous_image=$previous_image
backup_id=$backup_id
backup_path=$backup_path
migration_head=$migration_head
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
state=$state
EOF
  chmod 600 "$temp"
  mv "$temp" "$file"
}

miemie_activate_release() {
  local manifest="$1" temp="$MIEMIE_RELEASE_STATE_DIR/current.env.tmp.$$"
  cp "$manifest" "$temp"
  chmod 600 "$temp"
  mv "$temp" "$MIEMIE_RELEASE_STATE_DIR/current.env"
}

miemie_create_backup() {
  local output backup_id relative checksum actual_checksum host_path
  output="$(miemie_compose run --rm -T worker-ops python - <<'PY'
from app.services.ops_runner import build_ops_runner
from app.services.platform_operations import build_platform_operations_service
ops = build_platform_operations_service()
run, _ = ops.queue_operation(operation_type="backup", source="cli")
result = build_ops_runner().run_backup(run.id)
if result is None or result.status != "succeeded" or not result.local_path_relative or not result.sha256:
    raise SystemExit("backup failed")
print("\t".join([result.id, result.local_path_relative, result.sha256]))
PY
)" || return 1
  IFS=$'\t' read -r backup_id relative checksum <<< "$(printf '%s\n' "$output" | tail -n 1)"
  [[ -n "$backup_id" && -n "$relative" && -n "$checksum" ]] || return 1
  host_path="$MIEMIE_INSTALL_ROOT/backups/$relative"
  [[ -s "$host_path" ]] || return 1
  actual_checksum="$(miemie_sha256 "$host_path")"
  [[ "$actual_checksum" == "$checksum" ]] || { echo "backup checksum verification failed" >&2; return 1; }
  [[ -f "$host_path.sha256" ]] || { echo "backup checksum sidecar missing" >&2; return 1; }
  [[ "$(awk '{print $1}' "$host_path.sha256")" == "$checksum" ]] || {
    echo "backup checksum sidecar mismatch" >&2
    return 1
  }
  printf '%s\t%s\t%s\n' "$backup_id" "$relative" "$checksum"
}

miemie_resolve_backup() {
  local requested="$1" root candidate resolved
  root="$(readlink -f "$MIEMIE_INSTALL_ROOT/backups")"
  if [[ "$requested" = /* ]]; then
    candidate="$requested"
  else
    candidate="$root/$requested"
  fi
  resolved="$(readlink -f "$candidate" 2>/dev/null || true)"
  [[ -n "$resolved" && -s "$resolved" ]] || { echo "backup not found" >&2; return 2; }
  case "$resolved" in "$root"/*) ;; *) echo "backup must be inside $root" >&2; return 2 ;; esac
  printf '%s' "$resolved"
}

miemie_confirm_restore() {
  local backup_name="$1" expected_name="${MIEMIE_RESTORE_CONFIRM_BACKUP:-}" phrase="${MIEMIE_RESTORE_CONFIRM_PHRASE:-}"
  if [[ -z "$expected_name" ]]; then read -r -p "Type backup filename $backup_name: " expected_name; fi
  if [[ -z "$phrase" ]]; then read -r -p "Type RESTORE MIEMIE DATABASE: " phrase; fi
  [[ "$expected_name" == "$backup_name" && "$phrase" == "RESTORE MIEMIE DATABASE" ]] || {
    echo "restore confirmation mismatch" >&2
    return 2
  }
}

miemie_confirm_purge() {
  local phrase="${MIEMIE_PURGE_CONFIRMATION:-}"
  if [[ -z "$phrase" ]]; then read -r -p "Type DELETE MIEMIE DATA: " phrase; fi
  [[ "$phrase" == "DELETE MIEMIE DATA" ]] || { echo "purge confirmation mismatch" >&2; return 2; }
}

miemie_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

miemie_assert_safe_purge_path() {
  local path="$1" resolved
  resolved="$(readlink -f "$path" 2>/dev/null || true)"
  [[ -n "$resolved" ]] || { echo "purge path does not exist: $path" >&2; return 2; }
  case "$resolved" in
    /|/opt|/usr|/var|/etc|/var/lib|/var/log|/usr/local|/usr/local/bin)
      echo "unsafe purge path: $resolved" >&2
      return 2
      ;;
  esac
  printf '%s' "$resolved"
}
