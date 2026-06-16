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
MIEMIE_PREFLIGHT_SCOPE="${MIEMIE_PREFLIGHT_SCOPE:-full}"

mkdir -p "$ARTIFACT_DIR" "$TMP_DIR"

STATUS_FILE="$ARTIFACT_DIR/status.json"
RESULTS_FILE="$ARTIFACT_DIR/results.tsv"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
REMEDIATION_FILE="$ARTIFACT_DIR/remediation.md"
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
  "scope": "$(json_escape "$MIEMIE_PREFLIGHT_SCOPE")",
  "dns_a": "$(json_escape "$dns_summary")",
  "route_origin": "$(json_escape "$route_summary")",
  "public_health": "$(json_escape "$health_summary")",
  "remediation_file": "$(json_escape "$REMEDIATION_FILE")",
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

write_remediation_summary() {
  local state="$1"
  local route_detail route_uses_wide_tun_route
  route_detail=""
  route_uses_wide_tun_route="false"
  if [[ -f "$ARTIFACT_DIR/route-origin.txt" ]]; then
    route_detail="$(grep -E 'destination:|mask:|gateway:|interface:' "$ARTIFACT_DIR/route-origin.txt" 2>/dev/null | tr '\n' ' ' | sed 's/[[:space:]]*$//' || true)"
    if grep -Eq 'destination:[[:space:]]*32\.0\.0\.0' "$ARTIFACT_DIR/route-origin.txt" \
      && grep -Eq 'mask:[[:space:]]*224\.0\.0\.0' "$ARTIFACT_DIR/route-origin.txt"; then
      route_uses_wide_tun_route="true"
    fi
  fi
  {
    printf '# Pre-studio Connectivity Remediation\n\n'
    printf -- '- Run ID: `%s`\n' "$RUN_ID"
    printf -- '- State: `%s`\n' "$state"
    printf -- '- Host: `%s`\n' "$HOST"
    printf -- '- Origin IP: `%s`\n' "$ORIGIN_IP"
    printf -- '- SSH target: `%s`\n\n' "$SSH_TARGET"
    printf -- '- Scope: `%s`\n\n' "$MIEMIE_PREFLIGHT_SCOPE"

    printf '## Results\n\n'
    if [[ -f "$RESULTS_FILE" ]]; then
      sed 's/\t/ | /g' "$RESULTS_FILE"
    else
      printf 'No results were written.\n'
    fi

    printf '\n## Recommended Next Steps\n\n'
    if [[ "$state" == "passed" ]]; then
      if [[ "$MIEMIE_PREFLIGHT_SCOPE" == "network" ]]; then
        printf -- '- Network-only checks are clear. Continue with the full preflight: `scripts/pre_studio_connectivity_preflight.sh`.\n'
      else
        printf -- '- Connectivity is clear. Continue with `CONFIRM_REMOTE_SEQUENCE=run scripts/pre_studio_remote_postgres_sequence.sh`.\n'
      fi
      return
    fi
    if [[ "$state" == "dry_run" ]]; then
      printf -- '- Dry run only. Re-run without `MIEMIE_PREFLIGHT_DRY_RUN=true` to execute network checks.\n'
      return
    fi

    if grep -Eq '^dns[[:space:]]+blocked[[:space:]]+fake-ip detected' "$RESULTS_FILE"; then
      printf -- '- DNS is returning a Clash fake-IP (`198.18.0.0/15`). Disable TUN/fake-IP for this run, or configure `pre-studio.miemie.co` to bypass proxy DNS. Re-check with `dig +short pre-studio.miemie.co A` until it returns real Cloudflare A records instead of `198.18.*`.\n'
    fi
    if grep -Eq '^route[[:space:]]+blocked[[:space:]]+TUN/fake-ip route detected' "$RESULTS_FILE"; then
      printf -- '- Route to the origin IP is still going through TUN/fake-IP. Add a direct route/bypass for `%s` or temporarily disable Clash TUN, then re-check `route -n get %s` until the interface is the physical network interface, not `utun*`.\n' "$ORIGIN_IP" "$ORIGIN_IP"
      printf -- '- Recommended Clash rule: `IP-CIDR,%s/32,DIRECT,no-resolve`. Put it before broad proxy/fake-IP rules and before any Rule Providers that may catch `32.0.0.0/3` or other large IP ranges.\n' "$ORIGIN_IP"
      if [[ "$route_uses_wide_tun_route" == "true" ]]; then
        printf -- '- Current route looks like the wide TUN catch-all range `32.0.0.0/3` is still winning over the host-specific rule. Route detail: `%s`.\n' "$route_detail"
      fi
    fi
    if grep -Eq '^tcp_ssh[[:space:]]+passed' "$RESULTS_FILE" && grep -Eq '^ssh_banner[[:space:]]+blocked' "$RESULTS_FILE"; then
      printf -- '- TCP 22 is reachable but SSH banner did not complete. After DNS/route are clean, retry SSH. If it still blocks, check Alibaba Cloud security group, server firewall, sshd limits, and `/var/log/auth.log` on the origin host.\n'
    elif grep -Eq '^tcp_ssh[[:space:]]+(failed|blocked)' "$RESULTS_FILE"; then
      printf -- '- TCP 22 is not reachable from this client. Check local network policy first, then cloud security group/firewall rules for `%s:%s`.\n' "$ORIGIN_IP" "$SSH_PORT"
    fi
    if grep -Eq '^public_health[[:space:]]+failed' "$RESULTS_FILE"; then
      printf -- '- Public health timed out or failed from this client. Once DNS/route are clean, retry `curl --noproxy "*" -k -sS -D - -o /tmp/pre-studio-health.json --connect-timeout 10 --max-time 20 https://pre-studio.miemie.co/api/health`. If only this local network fails, verify from a target-market VPS or the server itself before changing application code.\n'
    elif grep -Eq '^public_health[[:space:]]+blocked' "$RESULTS_FILE"; then
      printf -- '- Public health could not be validated because a required local tool is missing. Install the missing tool or run the preflight on a prepared operator machine.\n'
    fi
    if [[ "$MIEMIE_PREFLIGHT_SCOPE" == "network" ]]; then
      printf -- '- This was a network-only check. It intentionally stopped before TCP/SSH/public-health validation; run full preflight after DNS and route are clean.\n'
    fi

    printf '\nDo not run the remote PostgreSQL sequence until this preflight exits `0`.\n'
  } > "$REMEDIATION_FILE"
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

  case "$MIEMIE_PREFLIGHT_SCOPE" in
    full|network)
      record_result "scope" "passed" "$MIEMIE_PREFLIGHT_SCOPE"
      ;;
    *)
      record_result "scope" "blocked" "unsupported MIEMIE_PREFLIGHT_SCOPE=$MIEMIE_PREFLIGHT_SCOPE"
      write_remediation_summary "blocked"
      write_status "blocked" "precheck" "unsupported MIEMIE_PREFLIGHT_SCOPE"
      return 2
      ;;
  esac

  if [[ "$MIEMIE_PREFLIGHT_DRY_RUN" == "true" ]]; then
    record_result "dry_run" "passed" "no network checks executed"
    write_remediation_summary "dry_run"
    write_status "dry_run" "planned" "set MIEMIE_PREFLIGHT_DRY_RUN=false to execute checks"
    return 0
  fi

  local failures=0
  check_dns || failures=$((failures + 1))
  check_route || failures=$((failures + 1))

  if [[ "$MIEMIE_PREFLIGHT_SCOPE" == "network" ]]; then
    if [[ "$failures" == "0" ]]; then
      write_remediation_summary "passed"
      write_status "passed" "network" ""
      return 0
    fi
    write_remediation_summary "blocked"
    write_status "blocked" "network" "$failures network check(s) failed or blocked"
    return 2
  fi

  check_tcp_ssh || failures=$((failures + 1))
  check_ssh_banner || failures=$((failures + 1))
  check_public_health || failures=$((failures + 1))

  if [[ "$failures" == "0" ]]; then
    write_remediation_summary "passed"
    write_status "passed" "done" ""
    return 0
  fi
  write_remediation_summary "blocked"
  write_status "blocked" "connectivity" "$failures preflight check(s) failed or blocked"
  return 2
}

main "$@"
