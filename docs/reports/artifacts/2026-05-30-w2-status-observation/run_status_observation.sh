#!/usr/bin/env bash
set -u

RUN_ID="${RUN_ID:-w2-status-observation-$(date +%Y%m%d-%H%M%S)}"
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
TASK_ID=""
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
    echo "## k6"
    k6 version || true
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
  if ! command -v k6 >/dev/null 2>&1; then
    fail_run "k6 is not installed"
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
  local suffix register_body register_status project_body project_status task_body task_status status_body
  suffix="$(date +%m%d%H%M%S)-$RANDOM"
  USERNAME="w2obs_${suffix}"
  PASSWORD="W2Obs_${suffix}_$(date +%s)"
  register_body="${BASE_DIR}/register-response.raw.json"
  project_body="${BASE_DIR}/project-response.raw.json"
  task_body="${BASE_DIR}/task-response.raw.json"
  status_body="${BASE_DIR}/task-status-snapshot.json"

  register_status="$(safe_curl -o "${register_body}" -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -X POST "${LOCAL_BASE}/api/auth/register" \
    -d "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\",\"display_name\":\"W2状态观察\"}" || true)"
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
    -d "{\"name\":\"W2 状态观察阶梯 ${suffix}\",\"description\":\"W2平台侧状态观察阶梯压测临时项目\"}" || true)"
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

  task_status="$(safe_curl -o "${task_body}" -w '%{http_code}' \
    -H "Authorization: Bearer ${TOKEN}" \
    -H 'Content-Type: application/json' \
    -X POST "${LOCAL_BASE}/api/video-studio" \
    -d "{\"project_id\":\"${PROJECT_ID}\",\"task_type\":\"text_to_video\",\"prompt\":\"W2状态观察阶梯平台侧无key任务\",\"group_count\":1}" || true)"
  if [ "${task_status}" != "200" ]; then
    fail_run "create video task status ${task_status}"
    return 1
  fi
  TASK_ID="$(python3 - "${task_body}" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
print((data.get("task") or {}).get("id", ""))
PY
)"
  python3 - "${task_body}" "${BASE_DIR}/task-summary.json" <<'PY'
import json, sys
data = (json.load(open(sys.argv[1], encoding="utf-8")).get("task") or {})
keep = [
    "id", "project_id", "name", "task_type", "task_kind", "provider",
    "model_id", "status", "submit_state", "created_at", "updated_at",
]
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps({
    k: data.get(k) for k in keep
}, ensure_ascii=False, indent=2))
PY
  rm -f "${task_body}"
  if [ -z "${TASK_ID}" ]; then
    fail_run "empty task id"
    return 1
  fi

  sleep 3
  safe_curl -o "${status_body}" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${LOCAL_BASE}/api/video-studio/${TASK_ID}/status" || true

  log_event "prepare data ok project=${PROJECT_ID} task=${TASK_ID}"
}

gate_summary() {
  python3 - "$1" "$2" "$3" "$4" "$5" "$6" <<'PY'
import json, sys
summary_path, gate_path, label, vus, duration, rc = sys.argv[1:7]
data = json.load(open(summary_path, encoding="utf-8"))
metrics = data.get("metrics", {})
duration_metric = metrics.get("http_req_duration", {})
failed = float((metrics.get("http_req_failed") or {}).get("value") or 0)
p95 = float(duration_metric.get("p(95)") or 0)
p99 = float(duration_metric.get("p(99)") or 0)
count = int((metrics.get("http_reqs") or {}).get("count") or 0)
checks_fails = int((metrics.get("checks") or {}).get("fails") or 0)
ok = failed < 0.01 and p95 < 300 and checks_fails == 0 and int(rc) == 0
reason = ""
if failed >= 0.01:
    reason = f"http_req_failed {failed:.6f} >= 0.01"
elif p95 >= 300:
    reason = f"p95 {p95:.2f}ms >= 300ms"
elif checks_fails:
    reason = f"checks_fails {checks_fails}"
elif int(rc) != 0:
    reason = f"k6 exit {rc}"
out = {
    "label": label,
    "vus": int(vus),
    "duration": duration,
    "http_req_failed": failed,
    "http_req_duration_p95_ms": p95,
    "http_req_duration_p99_ms": p99,
    "http_reqs": count,
    "checks_fails": checks_fails,
    "k6_exit_code": int(rc),
    "ok": ok,
    "reason": reason,
}
open(gate_path, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=2))
print("\t".join([
    label, str(vus), duration, f"{failed:.9f}", f"{p95:.6f}",
    f"{p99:.6f}", str(count), str(checks_fails), "1" if ok else "0", reason,
]))
PY
}

run_stage() {
  local label="$1"
  local base_url="$2"
  local vus="$3"
  local duration="$4"
  local summary="${BASE_DIR}/${label}.summary.json"
  local log="${BASE_DIR}/${label}.log"
  local gate="${BASE_DIR}/${label}.gate.json"
  local query_urls="/api/projects,/api/video-studio?project_id=${PROJECT_ID},/api/video-studio/${TASK_ID},/api/video-studio/${TASK_ID}/status"
  CURRENT_STAGE="${label}"
  write_status "running" "$CURRENT_STAGE" ""
  log_event "stage ${label} start"

  MIEMIE_BASE_URL="${base_url}" \
  MIEMIE_AUTH_TOKEN="${TOKEN}" \
  LOADTEST_RUN_ID="${RUN_ID}" \
  SCENARIO_NAME="${label}" \
  MIEMIE_QUERY_URLS="${query_urls}" \
  K6_VUS="${vus}" \
  K6_DURATION="${duration}" \
  K6_SLEEP_SECONDS="2" \
    k6 run --summary-export "${summary}" "${K6_SCRIPT}" > "${log}" 2>&1
  local rc=$?

  local line
  line="$(gate_summary "${summary}" "${gate}" "${label}" "${vus}" "${duration}" "${rc}")"
  printf '%s\n' "${line}" >> "${RESULTS_FILE}"
  if python3 - "${gate}" <<'PY'
import json, sys
raise SystemExit(0 if json.load(open(sys.argv[1], encoding="utf-8")).get("ok") else 1)
PY
  then
    log_event "stage ${label} ok"
    return 0
  fi

  local reason
  reason="$(python3 - "${gate}" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("reason") or "gate failed")
PY
)"
  fail_run "${label}: ${reason}"
  return 1
}

run_ladder() {
  CURRENT_STAGE="status-ladder"
  write_status "running" "$CURRENT_STAGE" ""
  printf 'label\tvus\tduration\thttp_req_failed\tp95_ms\tp99_ms\thttp_reqs\tchecks_fails\tok\treason\n' > "${RESULTS_FILE}"

  run_stage "local-status-100" "${LOCAL_BASE}" "100" "120s" || return 1
  run_stage "public-status-100" "${PUBLIC_BASE}" "100" "120s" || return 1
  run_stage "local-status-300" "${LOCAL_BASE}" "300" "120s" || return 1
  run_stage "public-status-300" "${PUBLIC_BASE}" "300" "120s" || return 1
  run_stage "local-status-500" "${LOCAL_BASE}" "500" "120s" || return 1
  run_stage "public-status-500" "${PUBLIC_BASE}" "500" "120s" || return 1
}

capture_logs() {
  CURRENT_STAGE="capture-logs"
  write_status "running" "$CURRENT_STAGE" ""
  log_event "capture logs"
  docker logs --since "${START_ISO}" miemie-pre-api-1 > "${BASE_DIR}/api-status-observation-window.log" 2>&1 || true
  grep -E '"GET /api/(projects|video-studio)' "${BASE_DIR}/api-status-observation-window.log" \
    > "${BASE_DIR}/api-status-observation-excerpt.log" || true
  awk '/"GET \/api\/(projects|video-studio)/ {print $NF}' "${BASE_DIR}/api-status-observation-window.log" \
    | sort | uniq -c > "${BASE_DIR}/api-status-code-summary.txt" || true
}

cleanup() {
  CURRENT_STAGE="cleanup"
  write_status "running" "$CURRENT_STAGE" ""
  log_event "cleanup start"
  {
    echo "# cleanup"
    echo "date=$(date -Is)"
    if [ -n "${TASK_ID}" ]; then
      echo "## delete video task"
      safe_curl -o "${BASE_DIR}/delete-task-response.json" -w '%{http_code}\n' \
        -H "Authorization: Bearer ${TOKEN}" \
        -X DELETE "${LOCAL_BASE}/api/video-studio/${TASK_ID}" || true
    fi
    if [ -n "${PROJECT_ID}" ]; then
      echo "## delete project"
      safe_curl -o "${BASE_DIR}/delete-project-response.json" -w '%{http_code}\n' \
        -H "Authorization: Bearer ${TOKEN}" \
        -X DELETE "${LOCAL_BASE}/api/projects/${PROJECT_ID}" || true
    fi
    if [ -n "${TOKEN}" ]; then
      echo "## logout"
      safe_curl -o "${BASE_DIR}/logout-response.json" -w '%{http_code}\n' \
        -H "Authorization: Bearer ${TOKEN}" \
        -X POST "${LOCAL_BASE}/api/auth/logout" || true
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
  write_status "running" "init" ""
  log_event "run start"
  precheck || true
  if [ "${FAILED}" -eq 0 ]; then prepare_data || true; fi
  if [ "${FAILED}" -eq 0 ]; then run_ladder || true; fi
  capture_logs
  cleanup
  postcheck
  if [ "${FAILED}" -eq 0 ]; then
    write_status "passed" "done" ""
    log_event "run passed"
  else
    write_status "failed" "${CURRENT_STAGE}" "${FAIL_REASON}"
    log_event "run failed ${FAIL_REASON}"
  fi
}

main "$@"
