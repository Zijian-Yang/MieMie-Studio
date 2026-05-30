#!/usr/bin/env bash
set -u

RUN_ID="${RUN_ID:-w2-preview-rerun-$(date +%Y%m%d-%H%M%S)}"
BASE_DIR="${BASE_DIR:-/tmp/${RUN_ID}}"
APP_DIR="${APP_DIR:-/opt/miemie-pre}"
LOCAL_BASE="http://127.0.0.1:18100"
PUBLIC_BASE="https://pre-studio.miemie.co"
K6_SCRIPT="${APP_DIR}/loadtest/k6/s4-mixed-query-generate.js"
STATUS_FILE="${BASE_DIR}/status.json"
RESULTS_FILE="${BASE_DIR}/results.tsv"
EVENT_LOG="${BASE_DIR}/events.log"

mkdir -p "${BASE_DIR}"
chmod 700 "${BASE_DIR}"

TOKEN=""
PROJECT_ID=""
USERNAME=""
PASSWORD=""
FAILED=0
FAIL_REASON=""
CURRENT_STAGE="init"
START_ISO="$(date -Is)"

write_status() {
  python3 - "$STATUS_FILE" "$1" "$2" "${3:-}" <<'PY'
import json, pathlib, sys, time
path = pathlib.Path(sys.argv[1])
path.write_text(json.dumps({
    "state": sys.argv[2],
    "stage": sys.argv[3],
    "reason": sys.argv[4],
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
}, ensure_ascii=False, indent=2), encoding="utf-8")
PY
}

log_event() {
  printf '%s %s\n' "$(date -Is)" "$1" >> "${EVENT_LOG}"
}

fail_run() {
  FAILED=1
  FAIL_REASON="$1"
  log_event "FAIL ${FAIL_REASON}"
  write_status "failed" "${CURRENT_STAGE}" "${FAIL_REASON}"
}

safe_curl() {
  curl -sS --connect-timeout 10 --max-time 30 "$@"
}

metric_value() {
  python3 - "$1" "$2" "$3" <<'PY'
import json, sys
path, metric, key = sys.argv[1:4]
data = json.load(open(path, encoding="utf-8"))
metric_data = data.get("metrics", {}).get(metric, {})
if key == "value":
    print(metric_data.get("value", ""))
else:
    print(metric_data.get("percentiles", {}).get(key, metric_data.get(key, "")))
PY
}

precheck() {
  CURRENT_STAGE="precheck"
  write_status "running" "$CURRENT_STAGE" ""
  log_event "precheck start"
  {
    echo "# precheck"
    echo "run_id=${RUN_ID}"
    echo "date=$(date -Is)"
    echo "start_iso=${START_ISO}"
    echo
    echo "## git"
    git -C "${APP_DIR}" rev-parse HEAD || true
    echo
    echo "## health local"
    curl -sS -D "${BASE_DIR}/health-local-pre.headers" -o "${BASE_DIR}/health-local-pre.json" -w '%{http_code}\n' "${LOCAL_BASE}/api/health" || true
    echo
    echo "## health public"
    curl -sS -D "${BASE_DIR}/health-public-pre.headers" -o "${BASE_DIR}/health-public-pre.json" -w '%{http_code}\n' "${PUBLIC_BASE}/api/health" || true
    echo
    echo "## compose ps"
    cd "${APP_DIR}" && docker compose -p miemie-pre --env-file compose.env -f docker-compose.yml -f docker-compose.pre.override.yml ps || true
    echo
    echo "## docker stats"
    docker stats --no-stream || true
  } > "${BASE_DIR}/precheck.txt" 2>&1

  local local_code public_code
  local_code="$(curl -sS -o /dev/null -w '%{http_code}' "${LOCAL_BASE}/api/health" || true)"
  public_code="$(curl -sS -o /dev/null -w '%{http_code}' "${PUBLIC_BASE}/api/health" || true)"
  if [ "${local_code}" != "200" ]; then
    fail_run "local health is ${local_code}, expected 200"
    return 1
  fi
  if [ "${public_code}" != "200" ]; then
    fail_run "public health is ${public_code}, expected 200"
    return 1
  fi
  if [ ! -f "${K6_SCRIPT}" ]; then
    fail_run "missing k6 script ${K6_SCRIPT}"
    return 1
  fi
  log_event "precheck ok"
}

prepare_data() {
  CURRENT_STAGE="prepare-data"
  write_status "running" "$CURRENT_STAGE" ""
  log_event "prepare data start"
  local suffix register_body register_status project_body project_status
  suffix="$(date +%m%d%H%M%S)-$RANDOM"
  USERNAME="w2fix_${suffix}"
  PASSWORD="W2Fix_${suffix}_$(date +%s)"
  register_body="${BASE_DIR}/register-response.json"
  project_body="${BASE_DIR}/project-response.json"

  register_status="$(safe_curl -o "${register_body}" -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -X POST "${LOCAL_BASE}/api/auth/register" \
    -d "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\",\"display_name\":\"W2 preview复跑\"}" || true)"
  if [ "${register_status}" != "200" ]; then
    fail_run "register status ${register_status}"
    return 1
  fi
  TOKEN="$(python3 - "${register_body}" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("token", ""))
PY
)"
  python3 - "${register_body}" "${BASE_DIR}/register-summary.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps({
    "user": data.get("user", {}),
    "token_present": bool(data.get("token")),
}, ensure_ascii=False, indent=2))
PY
  rm -f "${register_body}"
  if [ -z "${TOKEN}" ]; then
    fail_run "empty token"
    return 1
  fi

  cat > "${BASE_DIR}/env.sh" <<EOF
export MIEMIE_AUTH_TOKEN='${TOKEN}'
export MIEMIE_TEST_USERNAME='${USERNAME}'
export MIEMIE_TEST_PASSWORD='${PASSWORD}'
EOF
  chmod 600 "${BASE_DIR}/env.sh"

  project_status="$(safe_curl -o "${project_body}" -w '%{http_code}' \
    -H "Authorization: Bearer ${TOKEN}" \
    -H 'Content-Type: application/json' \
    -X POST "${LOCAL_BASE}/api/projects" \
    -d "{\"name\":\"W2 preview复跑 ${suffix}\",\"description\":\"配置并发写入修复后自动复跑\"}" || true)"
  if [ "${project_status}" != "200" ]; then
    fail_run "create project status ${project_status}"
    return 1
  fi
  PROJECT_ID="$(python3 - "${project_body}" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("id", ""))
PY
)"
  python3 - "${project_body}" "${BASE_DIR}/project-summary.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps({
    k: data.get(k) for k in ("id", "name", "description", "created_at", "updated_at")
}, ensure_ascii=False, indent=2))
PY
  rm -f "${project_body}"
  if [ -z "${PROJECT_ID}" ]; then
    fail_run "empty project id"
    return 1
  fi
  log_event "prepare data ok user=${USERNAME} project=${PROJECT_ID}"
}

run_preview_stage() {
  local label="$1"
  local base_url="$2"
  local vus="$3"
  local summary="${BASE_DIR}/${label}.summary.json"
  local raw="${BASE_DIR}/${label}.log"
  CURRENT_STAGE="${label}"
  write_status "running" "$CURRENT_STAGE" ""
  log_event "stage start ${label} base=${base_url} vus=${vus}"

  (
    cd "${APP_DIR}" && \
    K6_VUS="${vus}" \
    K6_DURATION="60s" \
    K6_SLEEP_SECONDS="2" \
    MIEMIE_BASE_URL="${base_url}" \
    MIEMIE_AUTH_TOKEN="${TOKEN}" \
    MIEMIE_QUERY_URLS="/api/projects,/api/video-studio?project_id=${PROJECT_ID}" \
    MIEMIE_SUBMIT_URL="/api/video-studio/preview-payload" \
    MIEMIE_SUBMIT_BODY="{\"project_id\":\"${PROJECT_ID}\",\"task_type\":\"text_to_video\",\"prompt\":\"W2配置并发修复preview复跑\",\"group_count\":1}" \
    MIEMIE_SUBMIT_EVERY="999999" \
    LOADTEST_RUN_ID="${RUN_ID}" \
    SCENARIO_NAME="${label}" \
    k6 run --summary-export "${summary}" "${K6_SCRIPT}"
  ) > "${raw}" 2>&1
  local k6_status=$?

  if [ ! -s "${summary}" ]; then
    fail_run "${label} missing k6 summary, k6_status=${k6_status}"
    return 1
  fi

  local fail_rate p95 p99
  fail_rate="$(metric_value "${summary}" "http_req_failed" "value")"
  p95="$(metric_value "${summary}" "http_req_duration" "p(95)")"
  p99="$(metric_value "${summary}" "http_req_duration" "p(99)")"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "${label}" "${base_url}" "${vus}" "${fail_rate}" "${p95}" "${p99}" >> "${RESULTS_FILE}"

  python3 - "${summary}" "${BASE_DIR}/${label}.gate.json" "${label}" "${k6_status}" <<'PY'
import json, sys
summary_path, out_path, label, k6_status = sys.argv[1:5]
data = json.load(open(summary_path, encoding="utf-8"))
metrics = data.get("metrics", {})
duration = metrics.get("http_req_duration", {})
failed = metrics.get("http_req_failed", {}).get("value")
p95 = duration.get("percentiles", {}).get("p(95)", duration.get("p(95)"))
p99 = duration.get("percentiles", {}).get("p(99)", duration.get("p(99)"))
gate = {
    "label": label,
    "k6_status": int(k6_status),
    "http_req_failed": failed,
    "http_req_duration_p95_ms": p95,
    "http_req_duration_p99_ms": p99,
    "p95_limit_ms": 800,
    "pass": bool(failed is not None and p95 is not None and failed < 0.01 and p95 < 800 and int(k6_status) == 0),
}
open(out_path, "w", encoding="utf-8").write(json.dumps(gate, ensure_ascii=False, indent=2))
PY
  local pass
  pass="$(python3 - "${BASE_DIR}/${label}.gate.json" <<'PY'
import json, sys
print("1" if json.load(open(sys.argv[1], encoding="utf-8")).get("pass") else "0")
PY
)"
  if [ "${pass}" != "1" ]; then
    fail_run "${label} gate failed: failed=${fail_rate}, p95=${p95}, k6_status=${k6_status}"
    return 1
  fi
  log_event "stage pass ${label} failed=${fail_rate} p95=${p95} p99=${p99}"
}

capture_preview_status() {
  local end_iso
  end_iso="$(date -Is)"
  {
    echo "start=${START_ISO}"
    echo "end=${end_iso}"
    docker logs --since "${START_ISO}" --until "${end_iso}" miemie-pre-api-1 2>&1 \
      | awk '/"POST \/api\/video-studio\/preview-payload HTTP\/1.1"/ {status=$NF; count[status]++} END {for (s in count) print s, count[s]}' \
      | sort
  } > "${BASE_DIR}/api-preview-status-summary.txt"
  docker logs --since "${START_ISO}" --until "${end_iso}" miemie-pre-api-1 2>&1 \
    | grep -E 'preview-payload| 5[0-9][0-9] |ERROR|Exception|FileNotFoundError' \
    > "${BASE_DIR}/api-preview-log-excerpt.log" || true
}

cleanup() {
  CURRENT_STAGE="cleanup"
  write_status "running" "$CURRENT_STAGE" ""
  log_event "cleanup start"
  {
    echo "# cleanup"
    echo "date=$(date -Is)"
    echo "project_id=${PROJECT_ID}"
    if [ -n "${TOKEN}" ] && [ -n "${PROJECT_ID}" ]; then
      echo "delete_project_status=$(curl -sS -o "${BASE_DIR}/delete-project-response.json" -w '%{http_code}' -H "Authorization: Bearer ${TOKEN}" -X DELETE "${LOCAL_BASE}/api/projects/${PROJECT_ID}" || true)"
    fi
    if [ -n "${TOKEN}" ]; then
      echo "logout_status=$(curl -sS -o "${BASE_DIR}/logout-response.json" -w '%{http_code}' -H "Authorization: Bearer ${TOKEN}" -X POST "${LOCAL_BASE}/api/auth/logout" || true)"
    fi
  } > "${BASE_DIR}/cleanup-summary.txt" 2>&1
  rm -f "${BASE_DIR}/env.sh"
  log_event "cleanup done"
}

postcheck() {
  CURRENT_STAGE="postcheck"
  write_status "running" "$CURRENT_STAGE" ""
  log_event "postcheck start"
  {
    echo "# postcheck"
    echo "date=$(date -Is)"
    echo
    echo "## health local"
    curl -sS -D "${BASE_DIR}/health-local-post.headers" -o "${BASE_DIR}/health-local-post.json" -w '%{http_code}\n' "${LOCAL_BASE}/api/health" || true
    echo
    echo "## health public"
    curl -sS -D "${BASE_DIR}/health-public-post.headers" -o "${BASE_DIR}/health-public-post.json" -w '%{http_code}\n' "${PUBLIC_BASE}/api/health" || true
    echo
    echo "## compose ps"
    cd "${APP_DIR}" && docker compose -p miemie-pre --env-file compose.env -f docker-compose.yml -f docker-compose.pre.override.yml ps || true
    echo
    echo "## docker stats"
    docker stats --no-stream || true
  } > "${BASE_DIR}/postcheck.txt" 2>&1
  log_event "postcheck done"
}

main() {
  printf 'label\tbase_url\tvus\thttp_req_failed\thttp_req_duration_p95_ms\thttp_req_duration_p99_ms\n' > "${RESULTS_FILE}"
  precheck || return 1
  prepare_data || return 1
  run_preview_stage "local-preview-10" "${LOCAL_BASE}" "10" || return 1
  run_preview_stage "public-preview-10" "${PUBLIC_BASE}" "10" || return 1
  run_preview_stage "local-preview-20" "${LOCAL_BASE}" "20" || return 1
  run_preview_stage "public-preview-20" "${PUBLIC_BASE}" "20" || return 1
  run_preview_stage "local-preview-30" "${LOCAL_BASE}" "30" || return 1
  run_preview_stage "public-preview-30" "${PUBLIC_BASE}" "30" || return 1
  capture_preview_status
  if grep -Eq '^5[0-9][0-9] ' "${BASE_DIR}/api-preview-status-summary.txt"; then
    fail_run "preview 5xx found"
    return 1
  fi
}

main
main_status=$?
capture_preview_status || true
cleanup
postcheck

if [ "${FAILED}" = "1" ] || [ "${main_status}" != "0" ]; then
  write_status "failed" "${CURRENT_STAGE}" "${FAIL_REASON:-main returned ${main_status}}"
  log_event "run failed status=${main_status} reason=${FAIL_REASON}"
  exit 1
fi

write_status "passed" "done" ""
log_event "run passed"
