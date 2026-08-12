#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/install_lib.sh
source "$SOURCE_ROOT/scripts/install_lib.sh"

MIEMIE_INSTALL_DRY_RUN="${MIEMIE_INSTALL_DRY_RUN:-false}"
MIEMIE_INSTALL_PREREQUISITES="${MIEMIE_INSTALL_PREREQUISITES:-true}"
MIEMIE_INSTALL_ROOT="${MIEMIE_INSTALL_ROOT:-/opt/miemie-studio}"
MIEMIE_INSTALL_CONFIG_DIR="${MIEMIE_INSTALL_CONFIG_DIR:-/etc/miemie}"
MIEMIE_INSTALL_STATE_DIR="${MIEMIE_INSTALL_STATE_DIR:-/var/lib/miemie/releases}"
MIEMIE_INSTALL_LOG_DIR="${MIEMIE_INSTALL_LOG_DIR:-/var/log/miemie}"
MIEMIE_INSTALL_BIN_DIR="${MIEMIE_INSTALL_BIN_DIR:-/usr/local/bin}"
MIEMIE_INSTALL_ARTIFACT_DIR="${MIEMIE_INSTALL_ARTIFACT_DIR:-/tmp/miemie-install-artifact}"
MIEMIE_HOST_PORT="${MIEMIE_HOST_PORT:-8000}"
MIEMIE_PROJECT_NAME="${MIEMIE_PROJECT_NAME:-miemie}"
MIEMIE_RUNTIME_UID="${MIEMIE_RUNTIME_UID:-10001}"
MIEMIE_RUNTIME_GID="${MIEMIE_RUNTIME_GID:-10001}"
# Default bind ownership is the fixed application identity 10001:10001.
MIEMIE_ENV_FILE="$MIEMIE_INSTALL_ROOT/compose.env"
MIEMIE_CURRENT_STAGE="precheck"

write_dry_run() {
  mkdir -p "$MIEMIE_INSTALL_ARTIFACT_DIR"
  cat > "$MIEMIE_INSTALL_ARTIFACT_DIR/plan.txt" <<'EOF'
host-preflight
prerequisites
source
configuration
permissions
build
database
administrator
services
health
cli
EOF
  cat > "$MIEMIE_INSTALL_ARTIFACT_DIR/status.json" <<EOF
{"state":"dry_run","stage":"planned","install_root":"$MIEMIE_INSTALL_ROOT"}
EOF
}

if [[ "$MIEMIE_INSTALL_DRY_RUN" == "true" ]]; then
  write_dry_run
  printf '[miemie] stage=planned state=dry_run\n'
  exit 0
fi

if [[ "$(id -u)" != "0" ]]; then
  miemie_fail "root_required"
  exit 2
fi

mkdir -p "$MIEMIE_INSTALL_LOG_DIR"
chmod 700 "$MIEMIE_INSTALL_LOG_DIR"
exec > >(tee -a "$MIEMIE_INSTALL_LOG_DIR/install.log") 2>&1

trap 'rc=$?; if [[ $rc -ne 0 ]]; then printf "[miemie] stage=%s state=failed reason=exit_%s next=sudo_%s/install.sh\n" "${MIEMIE_CURRENT_STAGE:-unknown}" "$rc" "$SOURCE_ROOT"; fi' EXIT

miemie_stage host-preflight
miemie_supported_host || miemie_fail "unsupported_host"
case "$(uname -m)" in x86_64|aarch64|arm64) ;; *) miemie_fail "unsupported_arch" ;; esac
available_kb="$(df -Pk "$(dirname "$MIEMIE_INSTALL_ROOT")" 2>/dev/null | awk 'NR==2 {print $4}' || true)"
if [[ -n "$available_kb" && "$available_kb" -lt 20971520 ]]; then
  printf '[miemie] stage=host-preflight state=warning reason=disk_below_20gb\n'
fi
if [[ ! -d "$MIEMIE_INSTALL_ROOT" ]] && command -v ss >/dev/null 2>&1 && ss -ltn "sport = :$MIEMIE_HOST_PORT" | grep -q LISTEN; then
  miemie_fail "host_port_in_use"
fi

miemie_stage prerequisites
if [[ "$MIEMIE_INSTALL_PREREQUISITES" == "true" ]]; then
  miemie_install_prerequisites
fi
for command in git curl docker; do command -v "$command" >/dev/null 2>&1 || miemie_fail "${command}_missing"; done
docker compose version >/dev/null 2>&1 || miemie_fail "compose_missing"

miemie_stage source
if [[ -n "$(git -C "$SOURCE_ROOT" status --porcelain --untracked-files=no)" ]]; then
  miemie_fail "source_tracked_changes"
fi
source_commit="$(git -C "$SOURCE_ROOT" rev-parse HEAD)"
if [[ "$SOURCE_ROOT" != "$MIEMIE_INSTALL_ROOT" && ! -d "$MIEMIE_INSTALL_ROOT/.git" ]]; then
  origin_url="$(git -C "$SOURCE_ROOT" remote get-url origin)"
  mkdir -p "$(dirname "$MIEMIE_INSTALL_ROOT")"
  git clone --branch pre --single-branch "$origin_url" "$MIEMIE_INSTALL_ROOT"
  git -C "$MIEMIE_INSTALL_ROOT" fetch origin "$source_commit"
  git -C "$MIEMIE_INSTALL_ROOT" checkout -B pre "$source_commit"
fi
[[ -d "$MIEMIE_INSTALL_ROOT/.git" ]] || miemie_fail "install_source_missing"
install_commit="$(git -C "$MIEMIE_INSTALL_ROOT" rev-parse HEAD)"

miemie_stage configuration
if [[ ! -f "$MIEMIE_ENV_FILE" ]]; then
  postgres_password="$(miemie_random_urlsafe 32)"
  platform_key="$(miemie_random_urlsafe 32)"
  instance_id="miemie-$(miemie_random_urlsafe 9 | tr -d '=')"
  cp "$MIEMIE_INSTALL_ROOT/compose.env.example" "$MIEMIE_ENV_FILE"
  chmod 600 "$MIEMIE_ENV_FILE"
  miemie_set_env "$MIEMIE_ENV_FILE" MIEMIE_HOST_BIND 127.0.0.1
  miemie_set_env "$MIEMIE_ENV_FILE" MIEMIE_HOST_PORT "$MIEMIE_HOST_PORT"
  miemie_set_env "$MIEMIE_ENV_FILE" MIEMIE_PROJECT_NAME "$MIEMIE_PROJECT_NAME"
  miemie_set_env "$MIEMIE_ENV_FILE" MIEMIE_RUNTIME_UID "$MIEMIE_RUNTIME_UID"
  miemie_set_env "$MIEMIE_ENV_FILE" MIEMIE_RUNTIME_GID "$MIEMIE_RUNTIME_GID"
  miemie_set_env "$MIEMIE_ENV_FILE" MIEMIE_POSTGRES_PASSWORD "$postgres_password"
  miemie_set_env "$MIEMIE_ENV_FILE" MIEMIE_DATABASE_URL "postgresql+psycopg://miemie:${postgres_password}@postgres:5432/miemie"
  miemie_set_env "$MIEMIE_ENV_FILE" MIEMIE_PLATFORM_ENCRYPTION_KEY "$platform_key"
  miemie_set_env "$MIEMIE_ENV_FILE" MIEMIE_INSTANCE_ID "$instance_id"
fi
chmod 600 "$MIEMIE_ENV_FILE"
image="miemie-studio:pre-${install_commit:0:12}"
miemie_set_env "$MIEMIE_ENV_FILE" MIEMIE_IMAGE "$image"
miemie_set_env "$MIEMIE_ENV_FILE" MIEMIE_RUNTIME_GIT_COMMIT "$install_commit"

miemie_stage permissions
install -d -m 0750 "$MIEMIE_INSTALL_ROOT/backend/data" "$MIEMIE_INSTALL_ROOT/backend/logs" "$MIEMIE_INSTALL_ROOT/backups"
chown -R "$MIEMIE_RUNTIME_UID:$MIEMIE_RUNTIME_GID" "$MIEMIE_INSTALL_ROOT/backend/data" "$MIEMIE_INSTALL_ROOT/backend/logs" "$MIEMIE_INSTALL_ROOT/backups"

miemie_stage build
miemie_compose build migrate api worker worker-video worker-ops scheduler

miemie_stage database
miemie_compose up -d postgres redis
miemie_compose run --rm -T migrate

miemie_stage administrator
if ! miemie_compose run --rm -T api python -c 'from app.services.admin_bootstrap import bootstrap_status; raise SystemExit(0 if bootstrap_status()["admin_configured"] else 1)' >/dev/null; then
  admin_username="${MIEMIE_ADMIN_USERNAME:-}"
  admin_display_name="${MIEMIE_ADMIN_DISPLAY_NAME:-}"
  if [[ -z "$admin_username" ]]; then read -r -p 'Administrator username: ' admin_username; fi
  if [[ -z "${MIEMIE_ADMIN_PASSWORD:-}" ]]; then
    read -r -s -p 'Administrator password: ' MIEMIE_ADMIN_PASSWORD; printf '\n'
    read -r -s -p 'Confirm password: ' confirm_password; printf '\n'
    [[ "$MIEMIE_ADMIN_PASSWORD" == "$confirm_password" ]] || miemie_fail "admin_password_confirmation"
  fi
  export MIEMIE_ADMIN_PASSWORD
  admin_args=(bootstrap --username "$admin_username")
  if [[ -n "$admin_display_name" ]]; then
    admin_args+=(--display-name "$admin_display_name")
  fi
  miemie_compose run --rm -T -e MIEMIE_ADMIN_PASSWORD api python -m app.cli.admin "${admin_args[@]}"
  unset MIEMIE_ADMIN_PASSWORD confirm_password
fi

miemie_stage services
miemie_compose up -d --remove-orphans

miemie_stage health
for _ in $(seq 1 90); do
  if curl -fsS --connect-timeout 3 --max-time 5 "http://127.0.0.1:$MIEMIE_HOST_PORT/api/health" >/dev/null; then break; fi
  sleep 2
done
curl -fsS --connect-timeout 3 --max-time 5 "http://127.0.0.1:$MIEMIE_HOST_PORT/api/health" >/dev/null || miemie_fail "health_failed"

miemie_stage cli
install -d -m 0700 "$MIEMIE_INSTALL_CONFIG_DIR" "$MIEMIE_INSTALL_STATE_DIR"
cat > "$MIEMIE_INSTALL_CONFIG_DIR/miemie.conf.tmp" <<EOF
MIEMIE_INSTALL_ROOT=$MIEMIE_INSTALL_ROOT
MIEMIE_PROJECT_NAME=$MIEMIE_PROJECT_NAME
MIEMIE_ENV_FILE=$MIEMIE_ENV_FILE
MIEMIE_RELEASE_STATE_DIR=$MIEMIE_INSTALL_STATE_DIR
EOF
chmod 600 "$MIEMIE_INSTALL_CONFIG_DIR/miemie.conf.tmp"
mv "$MIEMIE_INSTALL_CONFIG_DIR/miemie.conf.tmp" "$MIEMIE_INSTALL_CONFIG_DIR/miemie.conf"
install -m 0755 "$MIEMIE_INSTALL_ROOT/scripts/miemie" "$MIEMIE_INSTALL_BIN_DIR/miemie"
printf 'commit=%s\nimage=%s\ninstalled_at=%s\nstate=healthy\n' "$install_commit" "$image" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$MIEMIE_INSTALL_STATE_DIR/current.env"
chmod 600 "$MIEMIE_INSTALL_STATE_DIR/current.env"

printf '[miemie] stage=complete state=passed endpoint=http://127.0.0.1:%s reverse_proxy_target=127.0.0.1:%s\n' "$MIEMIE_HOST_PORT" "$MIEMIE_HOST_PORT"
