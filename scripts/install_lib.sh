#!/usr/bin/env bash

miemie_stage() {
  MIEMIE_CURRENT_STAGE="$1"
  printf '[miemie] stage=%s state=running\n' "$MIEMIE_CURRENT_STAGE"
}

miemie_fail() {
  local reason="$1"
  printf '[miemie] stage=%s state=failed reason=%s\n' "${MIEMIE_CURRENT_STAGE:-unknown}" "$reason" >&2
  return 1
}

miemie_random_urlsafe() {
  head -c "${1:-32}" /dev/urandom | base64 | tr '+/' '-_' | tr -d '\n'
}

miemie_env_value() {
  local key="$1" file="$2"
  sed -n "s/^${key}=//p" "$file" | tail -n 1
}

miemie_set_env() {
  local file="$1" key="$2" value="$3" temp
  temp="${file}.tmp.$$"
  awk -v key="$key" -v value="$value" '
    BEGIN { replaced=0 }
    index($0, key "=")==1 { print key "=" value; replaced=1; next }
    { print }
    END { if (!replaced) print key "=" value }
  ' "$file" > "$temp"
  chmod 600 "$temp"
  mv "$temp" "$file"
}

miemie_previous_release_values() {
  local state_file="$1" env_file="$2" target_commit="$3"
  local current_commit current_image previous_commit previous_image
  if [[ -f "$state_file" ]]; then
    current_commit="$(miemie_env_value commit "$state_file")"
    current_image="$(miemie_env_value image "$state_file")"
    if [[ "$current_commit" == "$target_commit" ]]; then
      previous_commit="$(miemie_env_value previous_commit "$state_file")"
      previous_image="$(miemie_env_value previous_image "$state_file")"
    else
      previous_commit="$current_commit"
      previous_image="$current_image"
    fi
  else
    previous_commit="$(miemie_env_value MIEMIE_RUNTIME_GIT_COMMIT "$env_file")"
    previous_image="$(miemie_env_value MIEMIE_IMAGE "$env_file")"
  fi
  printf '%s\t%s\n' "$previous_commit" "$previous_image"
}

miemie_compose() {
  docker compose -p "$MIEMIE_PROJECT_NAME" --env-file "$MIEMIE_ENV_FILE" -f "$MIEMIE_INSTALL_ROOT/docker-compose.yml" "$@"
}

miemie_supported_host() {
  # Supported release labels: Ubuntu 22.04, Ubuntu 24.04, Debian 12.
  . /etc/os-release
  case "${ID}:${VERSION_ID}" in
    ubuntu:22.04|ubuntu:24.04|debian:12) return 0 ;;
    *) return 1 ;;
  esac
}

miemie_install_prerequisites() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y --no-install-recommends ca-certificates curl git gnupg openssl util-linux
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    return 0
  fi
  . /etc/os-release
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  local arch codename
  arch="$(dpkg --print-architecture)"
  codename="${VERSION_CODENAME}"
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/%s %s stable\n' \
    "$arch" "$ID" "$codename" > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}
