#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-pre-studio-connectivity-preflight-$(date +%Y%m%d%H%M%S)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r52-connectivity-preflight}"
TMP_DIR="${TMP_DIR:-/tmp/$RUN_ID}"
HOST="${HOST:-pre-studio.miemie.co}"
ORIGIN_IP="${ORIGIN_IP:-47.79.99.190}"
SSH_TARGET="${SSH_TARGET:-root@$ORIGIN_IP}"
SSH_PORT="${SSH_PORT:-22}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-12}"
PUBLIC_HEALTH_URL="${PUBLIC_HEALTH_URL:-https://$HOST/api/health}"
MIEMIE_PREFLIGHT_DRY_RUN="${MIEMIE_PREFLIGHT_DRY_RUN:-false}"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
RESULTS_FILE="$ARTIFACT_DIR/results.tsv"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
: > "$COMMAND_LOG"
printf 'check\tstate\tdetail\n' > "$RESULTS_FILE"

if [[ -x "backend/.venv/bin/python" ]]; then
  JSON_PYTHON="backend/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  JSON_PYTHON="python3"
else
  JSON_PYTHON=""
fi

json_escape() {
  if [[ -n "$JSON_PYTHON" ]]; then
    printf '%s' "$1" | "$JSON_PYTHON" -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
  else
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
  fi
}

log_cmd() {
  local label="$1"
  shift
  {
    printf '\n## [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$label"
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  } >> "$COMMAND_LOG"
}

record_result() {
  local check="$1"
  local state="$2"
  local detail="${3:-}"
  printf '%s\t%s\t%s\n' "$check" "$state" "$detail" >> "$RESULTS_FILE"
}

write_status() {
  local state="$1"
  local stage="$2"
  local reason="${3:-}"
  local dns_summary route_summary health_summary
  dns_summary=""
  route_summary=""
  health_summary=""
  if [[ -f "$ARTIFACT_DIR/dns-a.txt" ]]; then
    dns_summary="$(tr '\n' ' ' < "$ARTIFACT_DIR/dns-a.txt" | sed 's/[[:space:]]*$//')"
  fi
  if [[ -f "$ARTIFACT_DIR/route-origin.txt" ]]; then
    route_summary="$(grep -E 'gateway:|interface:' "$ARTIFACT_DIR/route-origin.txt" 2>/dev/null | tr '\n' ' ' | sed 's/[[:space:]]*$//' || true)"
  fi
  if [[ -f "$ARTIFACT_DIR/public-health-summary.txt" ]]; then
    health_summary="$(cat "$ARTIFACT_DIR/public-health-summary.txt")"
  fi
  cat > "$STATUS_FILE" <<JSON
{
  "run_id": "$(json_escape "$RUN_ID")",
  "state": "$(json_escape "$state")",
  "stage": "$(json_escape "$stage")",
  "reason": "$(json_escape "$reason")",
  "host": "$(json_escape "$HOST")",
  "origin_ip": "$(json_escape "$ORIGIN_IP")",
  "ssh_target": "$(json_escape "$SSH_TARGET")",
  "public_health_url": "$(json_escape "$PUBLIC_HEALTH_URL")",
  "dns_a": "$(json_escape "$dns_summary")",
  "route_origin": "$(json_escape "$route_summary")",
  "public_health": "$(json_escape "$health_summary")",
  "artifact_dir": "$(json_escape "$ARTIFACT_DIR")",
  "tmp_dir": "$(json_escape "$TMP_DIR")",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
}

sanitize_proxy_env() {
  {
    for key in HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy NO_PROXY no_proxy; do
      if [[ -n "${!key:-}" ]]; then
        printf '%s=<set>\n' "$key"
      else
        printf '%s=<unset>\n' "$key"
      fi
    done
  } > "$ARTIFACT_DIR/proxy-env.sanitized"
}

check_dns() {
  if ! command -v dig >/dev/null 2>&1; then
    record_result "dns" "blocked" "dig unavailable"
    return 1
  fi
  log_cmd "dns-a" dig +short "$HOST" A
  dig +short "$HOST" A > "$ARTIFACT_DIR/dns-a.txt" 2>"$ARTIFACT_DIR/dns-a.err" || {
    record_result "dns" "failed" "dig failed"
    return 1
  }
  if [[ ! -s "$ARTIFACT_DIR/dns-a.txt" ]]; then
    record_result "dns" "failed" "no A records"
    return 1
  fi
  if grep -Eq '^(198\.18\.|198\.19\.)' "$ARTIFACT_DIR/dns-a.txt"; then
    record_result "dns" "blocked" "fake-ip detected"
    return 1
  fi
  record_result "dns" "passed" "$(tr '\n' ' ' < "$ARTIFACT_DIR/dns-a.txt" | sed 's/[[:space:]]*$//')"
}

check_route() {
  if ! command -v route >/dev/null 2>&1; then
    record_result "route" "blocked" "route unavailable"
    return 1
  fi
  log_cmd "route-origin" route -n get "$ORIGIN_IP"
  route -n get "$ORIGIN_IP" > "$ARTIFACT_DIR/route-origin.txt" 2>"$ARTIFACT_DIR/route-origin.err" || {
    record_result "route" "failed" "route lookup failed"
    return 1
  }
  if grep -Eq 'interface:[[:space:]]*utun|gateway:[[:space:]]*198\.18\.' "$ARTIFACT_DIR/route-origin.txt"; then
    record_result "route" "blocked" "TUN/fake-ip route detected"
    return 1
  fi
  record_result "route" "passed" "$(grep -E 'gateway:|interface:' "$ARTIFACT_DIR/route-origin.txt" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
}

check_tcp_ssh() {
  if ! command -v nc >/dev/null 2>&1; then
    record_result "tcp_ssh" "blocked" "nc unavailable"
    return 1
  fi
  log_cmd "tcp-ssh" nc -vz "$ORIGIN_IP" "$SSH_PORT"
  nc -vz "$ORIGIN_IP" "$SSH_PORT" > "$ARTIFACT_DIR/tcp-ssh.out" 2>"$ARTIFACT_DIR/tcp-ssh.err" || {
    record_result "tcp_ssh" "failed" "tcp connect failed"
    return 1
  }
  record_result "tcp_ssh" "passed" "tcp $SSH_PORT reachable"
}

check_ssh_banner() {
  if ! command -v ssh >/dev/null 2>&1; then
    record_result "ssh_banner" "blocked" "ssh unavailable"
    return 1
  fi
  log_cmd "ssh-banner" ssh -o BatchMode=yes -o ConnectTimeout="$CONNECT_TIMEOUT" -o StrictHostKeyChecking=accept-new -p "$SSH_PORT" "$SSH_TARGET" "echo ok"
  ssh -o BatchMode=yes -o ConnectTimeout="$CONNECT_TIMEOUT" -o StrictHostKeyChecking=accept-new -p "$SSH_PORT" "$SSH_TARGET" "echo ok" \
    > "$ARTIFACT_DIR/ssh-banner.out" 2>"$ARTIFACT_DIR/ssh-banner.err" || {
    record_result "ssh_banner" "blocked" "$(head -n 1 "$ARTIFACT_DIR/ssh-banner.err" | tr '\t' ' ')"
    return 1
  }
  if ! grep -qx "ok" "$ARTIFACT_DIR/ssh-banner.out"; then
    record_result "ssh_banner" "failed" "unexpected ssh output"
    return 1
  fi
  record_result "ssh_banner" "passed" "remote command echo ok"
}

check_public_health() {
  if ! command -v curl >/dev/null 2>&1; then
    record_result "public_health" "blocked" "curl unavailable"
    return 1
  fi
  log_cmd "public-health" curl --noproxy "*" -k -sS -D "$ARTIFACT_DIR/public-health.headers" -o "$ARTIFACT_DIR/public-health.json" --connect-timeout "$CONNECT_TIMEOUT" --max-time 20 "$PUBLIC_HEALTH_URL"
  curl --noproxy "*" -k -sS -D "$ARTIFACT_DIR/public-health.headers" -o "$ARTIFACT_DIR/public-health.json" \
    --connect-timeout "$CONNECT_TIMEOUT" --max-time 20 "$PUBLIC_HEALTH_URL" \
    > "$ARTIFACT_DIR/public-health.curl.out" 2>"$ARTIFACT_DIR/public-health.curl.err" || {
    printf 'curl failed: %s' "$(head -n 1 "$ARTIFACT_DIR/public-health.curl.err" | tr '\t' ' ')" > "$ARTIFACT_DIR/public-health-summary.txt"
    record_result "public_health" "failed" "$(cat "$ARTIFACT_DIR/public-health-summary.txt")"
    return 1
  }

  if [[ -z "$JSON_PYTHON" ]]; then
    record_result "public_health" "blocked" "python unavailable for health JSON"
    return 1
  fi
  "$JSON_PYTHON" - "$ARTIFACT_DIR/public-health.headers" "$ARTIFACT_DIR/public-health.json" "$ARTIFACT_DIR/public-health-summary.txt" <<'PY'
import json
import sys
from pathlib import Path

headers_path, body_path, summary_path = map(Path, sys.argv[1:4])
headers = headers_path.read_text(encoding="utf-8", errors="replace")
payload = json.loads(body_path.read_text(encoding="utf-8"))
http_line = next((line.strip() for line in headers.splitlines() if line.startswith("HTTP/")), "")
request_id = ""
deployment = ""
for line in headers.splitlines():
    lower = line.lower()
    if lower.startswith("x-request-id:"):
        request_id = line.split(":", 1)[1].strip()
    if lower.startswith("x-deployment-version:"):
        deployment = line.split(":", 1)[1].strip()
summary = {
    "http": http_line,
    "status": payload.get("status"),
    "git_commit": payload.get("git_commit"),
    "redis_ok": payload.get("redis", {}).get("ok"),
    "x_request_id": bool(request_id),
    "x_deployment_version": bool(deployment),
}
summary_path.write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True), encoding="utf-8")
if payload.get("status") != "ok":
    raise SystemExit("health status is not ok")
if not request_id or not deployment:
    raise SystemExit("missing required response headers")
PY
  record_result "public_health" "passed" "$(cat "$ARTIFACT_DIR/public-health-summary.txt")"
}

main() {
  sanitize_proxy_env
  date -u +%Y-%m-%dT%H:%M:%SZ > "$ARTIFACT_DIR/time.txt"

  if [[ "$MIEMIE_PREFLIGHT_DRY_RUN" == "true" ]]; then
    write_status "dry_run" "planned" "set MIEMIE_PREFLIGHT_DRY_RUN=false to execute checks"
    record_result "dry_run" "passed" "no network checks executed"
    return 0
  fi

  local failures=0
  check_dns || failures=$((failures + 1))
  check_route || failures=$((failures + 1))
  check_tcp_ssh || failures=$((failures + 1))
  check_ssh_banner || failures=$((failures + 1))
  check_public_health || failures=$((failures + 1))

  if [[ "$failures" == "0" ]]; then
    write_status "passed" "done" ""
    return 0
  fi
  write_status "blocked" "connectivity" "$failures preflight check(s) failed or blocked"
  return 2
}

main "$@"
