#!/usr/bin/env bash
set -u

RUN_ID="${RUN_ID:-w2-staircase-$(date +%Y%m%d-%H%M%S)}"
BASE_DIR="${BASE_DIR:-/tmp/${RUN_ID}}"
APP_DIR="${APP_DIR:-/opt/miemie-pre}"
LOCAL_BASE="http://127.0.0.1:18100"
PUBLIC_BASE="https://pre-studio.miemie.co"
K6_SCRIPT="${APP_DIR}/loadtest/k6/s4-mixed-query-generate.js"
STATUS_FILE="${BASE_DIR}/status.json"
EVENT_LOG="${BASE_DIR}/events.log"
RESULTS_FILE="${BASE_DIR}/results.tsv"

mkdir -p "${BASE_DIR}"
chmod 700 "${BASE_DIR}"

TOKEN=""
PROJECT_ID=""
USERNAME=""
PASSWORD=""
FAILED=0
FAIL_REASON=""

json_string() {
  python3 - "$1" <<'PY'
import json, sys
print(json.dumps(sys.argv[1], ensure_ascii=False))
PY
}

write_status() {
  local state="$1"
  local stage="$2"
  local reason="${3:-}"
  python3 - "$STATUS_FILE" "$state" "$stage" "$reason" <<'PY'
import json, pathlib, sys, time
path = pathlib.Path(sys.argv[1])
data = {
    "state": sys.argv[2],
    "stage": sys.argv[3],
    "reason": sys.argv[4],
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
}
path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
PY
}

log_event() {
  local message="$1"
  printf '%s %s\n' "$(date -Is)" "$message" >> "${EVENT_LOG}"
}

fail_run() {
  FAILED=1
  FAIL_REASON="$1"
  log_event "FAIL ${FAIL_REASON}"
  write_status "failed" "${CURRENT_STAGE:-unknown}" "${FAIL_REASON}"
}

safe_curl() {
  curl -sS --connect-timeout 10 --max-time 30 "$@"
}

capture_precheck() {
  write_status "running" "precheck" ""
  log_event "precheck start"
  {
    echo "# precheck"
    echo "run_id=${RUN_ID}"
    echo "app_dir=${APP_DIR}"
    echo "date=$(date -Is)"
    echo
    echo "## git"
    git -C "${APP_DIR}" rev-parse HEAD || true
    git -C "${APP_DIR}" status --short --branch || true
    echo
    echo "## health local"
    curl -sS -D "${BASE_DIR}/health-local-pre.headers" -o "${BASE_DIR}/health-local-pre.json" -w '%{http_code}\n' "${LOCAL_BASE}/api/health" || true
    echo
    echo "## health public"
    curl -sS -D "${BASE_DIR}/health-public-pre.headers" -o "${BASE_DIR}/health-public-pre.json" -w '%{http_code}\n' "${PUBLIC_BASE}/api/health" || true
    echo
    echo "## k6"
    k6 version || true
    echo
    echo "## compose ps"
    docker compose -f "${APP_DIR}/docker-compose.pre.yml" ps || docker compose ps || true
    echo
    echo "## docker stats"
    docker stats --no-stream || true
  } > "${BASE_DIR}/precheck.txt" 2>&1

  local local_code public_code
  local_code="$(tail -n 1 "${BASE_DIR}/health-local-pre.json.code" 2>/dev/null || true)"
  public_code="$(tail -n 1 "${BASE_DIR}/health-public-pre.json.code" 2>/dev/null || true)"
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
  if ! command -v k6 >/dev/null 2>&1; then
    fail_run "k6 not installed on server"
    return 1
  fi
  if [ ! -f "${K6_SCRIPT}" ]; then
    fail_run "k6 script missing: ${K6_SCRIPT}"
    return 1
  fi
  log_event "precheck ok"
}

prepare_data() {
  write_status "running" "prepare-data" ""
  log_event "prepare data start"
  local suffix register_body register_status project_body project_status
  suffix="$(date +%m%d%H%M%S)-$RANDOM"
  USERNAME="w2_${suffix}"
  PASSWORD="W2Gate_${suffix}_$(date +%s)"
  register_body="${BASE_DIR}/register-response.json"
  project_body="${BASE_DIR}/project-response.json"

  register_status="$(safe_curl -o "${register_body}" -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -X POST "${LOCAL_BASE}/api/auth/register" \
    -d "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\",\"display_name\":\"W2 阶梯压测\"}" || true)"
  if [ "${register_status}" != "200" ]; then
    fail_run "register status ${register_status}"
    return 1
  fi

  TOKEN="$(python3 - "${register_body}" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("token", ""))
PY
)"
  if [ -z "${TOKEN}" ]; then
    fail_run "empty token after register"
    return 1
  fi
  python3 - "${register_body}" "${BASE_DIR}/register-summary.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = {"user": data.get("user", {}), "token_present": bool(data.get("token"))}
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps(summary, ensure_ascii=False, indent=2))
PY
  rm -f "${register_body}"

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
    -d "{\"name\":\"W2 阶梯压测基线 ${suffix}\",\"description\":\"自动化一次性项目，压测后删除\"}" || true)"
  if [ "${project_status}" != "200" ]; then
    fail_run "create project status ${project_status}"
    return 1
  fi
  PROJECT_ID="$(python3 - "${project_body}" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("id", ""))
PY
)"
  if [ -z "${PROJECT_ID}" ]; then
    fail_run "empty project id"
    return 1
  fi
  python3 - "${project_body}" "${BASE_DIR}/project-summary.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = {k: data.get(k) for k in ("id", "name", "description", "created_at", "updated_at")}
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps(summary, ensure_ascii=False, indent=2))
PY
  rm -f "${project_body}"
  log_event "prepare data ok user=${USERNAME} project=${PROJECT_ID}"
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

run_k6_stage() {
  local kind="$1"
  local label="$2"
  local base_url="$3"
  local vus="$4"
  local duration="$5"
  local p95_limit="$6"
  local summary="${BASE_DIR}/${label}.summary.json"
  local raw="${BASE_DIR}/${label}.log"
  local query_urls submit_url submit_body submit_every

  CURRENT_STAGE="${label}"
  write_status "running" "${label}" ""
  log_event "stage start ${label} kind=${kind} base=${base_url} vus=${vus} duration=${duration}"

  if [ "${kind}" = "read" ]; then
    query_urls="/api/projects,/api/studio?project_id=${PROJECT_ID},/api/video-studio?project_id=${PROJECT_ID}"
    submit_url=""
    submit_body=""
    submit_every="0"
  else
    query_urls="/api/projects,/api/video-studio?project_id=${PROJECT_ID}"
    submit_url="/api/video-studio/preview-payload"
    submit_body="{\"project_id\":\"${PROJECT_ID}\",\"task_type\":\"text_to_video\",\"prompt\":\"W2阶梯压测preview门禁\",\"group_count\":1}"
    submit_every="999999"
  fi

  (
    cd "${APP_DIR}" && \
    K6_VUS="${vus}" \
    K6_DURATION="${duration}" \
    K6_SLEEP_SECONDS="2" \
    MIEMIE_BASE_URL="${base_url}" \
    MIEMIE_AUTH_TOKEN="${TOKEN}" \
    MIEMIE_QUERY_URLS="${query_urls}" \
    MIEMIE_SUBMIT_URL="${submit_url}" \
    MIEMIE_SUBMIT_BODY="${submit_body}" \
    MIEMIE_SUBMIT_EVERY="${submit_every}" \
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
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "${label}" "${kind}" "${base_url}" "${vus}" "${duration}" "${fail_rate}" "${p95}" "${p99}" >> "${RESULTS_FILE}"

  python3 - "${summary}" "${BASE_DIR}/${label}.gate.json" "${label}" "${kind}" "${p95_limit}" "${k6_status}" <<'PY'
import json, sys
summary_path, out_path, label, kind, p95_limit, k6_status = sys.argv[1:7]
data = json.load(open(summary_path, encoding="utf-8"))
metrics = data.get("metrics", {})
failed = metrics.get("http_req_failed", {}).get("value")
duration = metrics.get("http_req_duration", {})
p95 = duration.get("percentiles", {}).get("p(95)", duration.get("p(95)"))
p99 = duration.get("percentiles", {}).get("p(99)", duration.get("p(99)"))
checks = metrics.get("checks", {})
checks_rate = checks.get("rate", checks.get("value"))
gate = {
    "label": label,
    "kind": kind,
    "k6_status": int(k6_status),
    "http_req_failed": failed,
    "http_req_duration_p95_ms": p95,
    "http_req_duration_p99_ms": p99,
    "checks_rate": checks_rate,
    "p95_limit_ms": float(p95_limit),
    "pass": bool(failed is not None and p95 is not None and failed < 0.01 and p95 < float(p95_limit) and int(k6_status) == 0),
}
open(out_path, "w", encoding="utf-8").write(json.dumps(gate, ensure_ascii=False, indent=2))
PY

  local gate_pass
  gate_pass="$(python3 - "${BASE_DIR}/${label}.gate.json" <<'PY'
import json, sys
print("1" if json.load(open(sys.argv[1], encoding="utf-8")).get("pass") else "0")
PY
)"
  if [ "${gate_pass}" != "1" ]; then
    fail_run "${label} gate failed: failed=${fail_rate}, p95=${p95}, k6_status=${k6_status}"
    return 1
  fi
  log_event "stage pass ${label} failed=${fail_rate} p95=${p95} p99=${p99}"
}

cleanup() {
  write_status "running" "cleanup" ""
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
  write_status "running" "postcheck" ""
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
    docker compose -f "${APP_DIR}/docker-compose.pre.yml" ps || docker compose ps || true
    echo
    echo "## docker stats"
    docker stats --no-stream || true
  } > "${BASE_DIR}/postcheck.txt" 2>&1
  log_event "postcheck done"
}

main() {
  printf 'label\tkind\tbase_url\tvus\tduration\thttp_req_failed\thttp_req_duration_p95_ms\thttp_req_duration_p99_ms\n' > "${RESULTS_FILE}"
  write_status "running" "init" ""
  cd "${APP_DIR}" || { fail_run "cannot cd ${APP_DIR}"; return 1; }
  capture_precheck || return 1
  prepare_data || return 1

  run_k6_stage "read" "local-read-50" "${LOCAL_BASE}" "50" "120s" "300" || return 1
  run_k6_stage "read" "public-read-50" "${PUBLIC_BASE}" "50" "120s" "300" || return 1
  run_k6_stage "read" "local-read-100" "${LOCAL_BASE}" "100" "180s" "300" || return 1
  run_k6_stage "read" "public-read-100" "${PUBLIC_BASE}" "100" "180s" "300" || return 1
  run_k6_stage "read" "local-read-200" "${LOCAL_BASE}" "200" "180s" "300" || return 1
  run_k6_stage "read" "public-read-200" "${PUBLIC_BASE}" "200" "180s" "300" || return 1

  run_k6_stage "preview" "local-preview-10" "${LOCAL_BASE}" "10" "60s" "800" || return 1
  run_k6_stage "preview" "public-preview-10" "${PUBLIC_BASE}" "10" "60s" "800" || return 1
  run_k6_stage "preview" "local-preview-20" "${LOCAL_BASE}" "20" "60s" "800" || return 1
  run_k6_stage "preview" "public-preview-20" "${PUBLIC_BASE}" "20" "60s" "800" || return 1
  run_k6_stage "preview" "local-preview-30" "${LOCAL_BASE}" "30" "60s" "800" || return 1
  run_k6_stage "preview" "public-preview-30" "${PUBLIC_BASE}" "30" "60s" "800" || return 1
}

main
main_status=$?
cleanup
postcheck

if [ "${FAILED}" = "1" ] || [ "${main_status}" != "0" ]; then
  write_status "failed" "${CURRENT_STAGE:-done}" "${FAIL_REASON:-main returned ${main_status}}"
  log_event "run failed status=${main_status} reason=${FAIL_REASON}"
  exit 1
fi

write_status "passed" "done" ""
log_event "run passed"
