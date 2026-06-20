#!/usr/bin/env bash

postgres_ops_alert_json_escape() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
  elif command -v python >/dev/null 2>&1; then
    printf '%s' "$1" | python -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
  else
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
  fi
}

postgres_ops_alert_append_event() {
  local artifact_dir="${ARTIFACT_DIR:-.}"
  local events_file="${artifact_dir}/alerts.tsv"
  mkdir -p "$artifact_dir"
  if [[ ! -f "$events_file" ]]; then
    printf 'time\tlabel\tseverity\tstate\tresult\tdetail\n' > "$events_file"
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "$1" "$2" "$3" "$4" "$5" >> "$events_file"
}

postgres_ops_send_alert() {
  local severity="$1"
  local label="$2"
  local state="$3"
  local reason="${4:-}"
  local artifact_dir="${5:-${ARTIFACT_DIR:-}}"
  local webhook_url="${MIEMIE_OPS_ALERT_WEBHOOK_URL:-}"
  local dry_run="${MIEMIE_OPS_ALERT_DRY_RUN:-false}"
  local run_id="${RUN_ID:-}"
  local host_name

  ARTIFACT_DIR="${artifact_dir:-${ARTIFACT_DIR:-.}}"
  host_name="$(hostname 2>/dev/null || printf 'unknown')"

  if [[ -z "$webhook_url" ]]; then
    postgres_ops_alert_append_event "$label" "$severity" "$state" "skipped" "no_webhook"
    return 0
  fi
  if [[ "$dry_run" == "true" ]]; then
    postgres_ops_alert_append_event "$label" "$severity" "$state" "skipped" "dry_run"
    return 0
  fi
  if ! command -v curl >/dev/null 2>&1; then
    postgres_ops_alert_append_event "$label" "$severity" "$state" "skipped" "curl_missing"
    return 0
  fi

  local payload
  payload="$(cat <<JSON
{"run_id":"$(postgres_ops_alert_json_escape "$run_id")","label":"$(postgres_ops_alert_json_escape "$label")","severity":"$(postgres_ops_alert_json_escape "$severity")","state":"$(postgres_ops_alert_json_escape "$state")","reason":"$(postgres_ops_alert_json_escape "$reason")","host":"$(postgres_ops_alert_json_escape "$host_name")","artifact_dir":"$(postgres_ops_alert_json_escape "$ARTIFACT_DIR")","time":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
JSON
)"

  if curl -fsS -X POST -H 'Content-Type: application/json' --data "$payload" --connect-timeout 5 --max-time 10 "$webhook_url" >/dev/null 2>&1; then
    postgres_ops_alert_append_event "$label" "$severity" "$state" "sent" "webhook"
  else
    postgres_ops_alert_append_event "$label" "$severity" "$state" "failed" "webhook_post_failed"
  fi
}
