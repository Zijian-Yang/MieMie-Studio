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
