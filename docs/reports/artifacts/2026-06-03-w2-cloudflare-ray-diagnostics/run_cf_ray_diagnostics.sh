#!/usr/bin/env bash
set -u

RUN_ID="${RUN_ID:-w2-cf-ray-diagnostics-$(date +%Y%m%d-%H%M%S)}"
BASE_DIR="${BASE_DIR:-/tmp/${RUN_ID}}"
APP_DIR="${APP_DIR:-/opt/miemie-pre}"
LOCAL_BASE="http://127.0.0.1:18100"
PUBLIC_BASE="https://pre-studio.miemie.co"
K6_SCRIPT="${BASE_DIR}/cf-ray-status.js"
STATUS_FILE="${BASE_DIR}/status.json"
RESULTS_FILE="${BASE_DIR}/results.tsv"
EVENT_LOG="${BASE_DIR}/events.log"
START_ISO="$(date -Is)"

mkdir -p "${BASE_DIR}"
chmod 700 "${BASE_DIR}"

TOKEN=""
PROJECT_ID=""
TASK_ID=""
FAILED=0
FAIL_REASON=""
CURRENT_STAGE="init"

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

safe_curl() {
  curl -sS --connect-timeout 10 --max-time 30 "$@"
}

fail_run() {
  FAILED=1
  FAIL_REASON="$1"
  log_event "FAIL ${FAIL_REASON}"
  write_status "failed" "${CURRENT_STAGE}" "${FAIL_REASON}"
}

write_k6_script() {
  cat > "${K6_SCRIPT}" <<'JS'
import http from 'k6/http'
import { check, fail, sleep } from 'k6'

const baseUrl = (__ENV.MIEMIE_BASE_URL || 'https://pre-studio.miemie.co').replace(/\/$/, '')
const authToken = (__ENV.MIEMIE_AUTH_TOKEN || '').trim()
const loadtestRunId = (__ENV.LOADTEST_RUN_ID || 'w2-cf-ray-diagnostics')
const scenarioName = (__ENV.SCENARIO_NAME || 'cf-ray-status-100')
const slowThresholdMs = Number(__ENV.SLOW_SAMPLE_MS || 800)
const queryUrls = (__ENV.MIEMIE_QUERY_URLS || '')
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean)

export const options = {
  vus: Number(__ENV.K6_VUS || 100),
  duration: __ENV.K6_DURATION || '120s',
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<300'],
  },
}

function buildHeaders(operation) {
  const requestId = `${loadtestRunId}-${scenarioName}-${operation}-${__VU}-${__ITER}`
  const headers = {
    'Content-Type': 'application/json',
    'X-Request-ID': requestId,
  }
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`
  }
  return { headers, requestId }
}

function getHeader(response, headerName) {
  const expected = headerName.toLowerCase()
  for (const key of Object.keys(response.headers || {})) {
    if (key.toLowerCase() === expected) {
      return response.headers[key]
    }
  }
  return ''
}

function hasHeader(response, headerName) {
  return Boolean(getHeader(response, headerName))
}

function emitSample(kind, queryUrl, response, requestId) {
  const payload = {
    kind,
    request_id: requestId,
    vu: __VU,
    iter: __ITER,
    url: queryUrl,
    status: response.status,
    error: response.error || '',
    error_code: response.error_code || 0,
    duration_ms: response.timings ? response.timings.duration : null,
    blocked_ms: response.timings ? response.timings.blocked : null,
    connecting_ms: response.timings ? response.timings.connecting : null,
    tls_ms: response.timings ? response.timings.tls_handshaking : null,
    waiting_ms: response.timings ? response.timings.waiting : null,
    receiving_ms: response.timings ? response.timings.receiving : null,
    cf_ray: getHeader(response, 'CF-Ray'),
    cf_cache_status: getHeader(response, 'CF-Cache-Status'),
    server: getHeader(response, 'Server'),
  }
  console.log(`${kind} ${JSON.stringify(payload)}`)
}

export default function () {
  if (!queryUrls.length) {
    fail('必须提供 MIEMIE_QUERY_URLS')
  }
  for (const queryUrl of queryUrls) {
    const { headers, requestId } = buildHeaders('query')
    const response = http.get(`${baseUrl}${queryUrl}`, { headers })
    if (response.status === 0 || response.error) {
      emitSample('FAIL_SAMPLE', queryUrl, response, requestId)
    } else if (response.timings && response.timings.duration >= slowThresholdMs) {
      emitSample('SLOW_SAMPLE', queryUrl, response, requestId)
    }
    check(response, {
      'query status acceptable': (current) => current.status >= 200 && current.status < 400,
      'query has request id': (current) => hasHeader(current, 'X-Request-ID'),
      'query has deployment version': (current) => hasHeader(current, 'X-Deployment-Version'),
    })
  }
  sleep(Number(__ENV.K6_SLEEP_SECONDS || 2))
}
JS
}

precheck() {
  CURRENT_STAGE="precheck"
  write_status "running" "$CURRENT_STAGE" ""
  log_event "precheck start"
  write_k6_script
  {
    echo "# precheck"
    echo "run_id=${RUN_ID}"
    echo "date=$(date -Is)"
    echo "start_iso=${START_ISO}"
    echo
    echo "## dns"
    dig +short pre-studio.miemie.co A || true
    echo
    echo "## health public cloudflare"
    curl -sS -D "${BASE_DIR}/health-public-pre.headers" -o "${BASE_DIR}/health-public-pre.json" -w '%{http_code}\n' "${PUBLIC_BASE}/api/health" || true
    echo
    echo "## git"
    git -C "${APP_DIR}" rev-parse HEAD || true
    echo
    echo "## runtime commit"
    grep -n "MIEMIE_RUNTIME_GIT_COMMIT" "${APP_DIR}/compose.env" || true
    echo
    echo "## k6"
    k6 version || true
    echo
    echo "## compose ps"
    cd "${APP_DIR}" && docker compose -p miemie-pre --env-file compose.env -f docker-compose.yml -f docker-compose.pre.override.yml ps || true
    echo
    echo "## docker stats"
    docker stats --no-stream || true
  } > "${BASE_DIR}/precheck.txt" 2>&1

  local code server_header
  code="$(curl -sS -o /dev/null -w '%{http_code}' "${PUBLIC_BASE}/api/health" || true)"
  server_header="$(grep -Ei '^server:' "${BASE_DIR}/health-public-pre.headers" | head -1 || true)"
  if [ "${code}" != "200" ]; then
    fail_run "public health is ${code}, expected 200"
    return 1
  fi
  if ! printf '%s' "${server_header}" | grep -qi cloudflare; then
    fail_run "not served by cloudflare: ${server_header}"
    return 1
  fi
  log_event "precheck ok"
}

prepare_data() {
  CURRENT_STAGE="prepare-data"
  write_status "running" "$CURRENT_STAGE" ""
  log_event "prepare data start"
  local suffix register_body register_status project_body project_status task_body task_status username password
  suffix="$(date +%m%d%H%M%S)-$RANDOM"
  username="w2cfdiag_${suffix}"
  password="W2CfDiag_${suffix}_$(date +%s)"
  register_body="${BASE_DIR}/register-response.raw.json"
  project_body="${BASE_DIR}/project-response.raw.json"
  task_body="${BASE_DIR}/task-response.raw.json"

  register_status="$(safe_curl -o "${register_body}" -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -X POST "${LOCAL_BASE}/api/auth/register" \
    -d "{\"username\":\"${username}\",\"password\":\"${password}\",\"display_name\":\"W2 Cloudflare Diagnostics\"}" || true)"
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
export MIEMIE_TEST_USERNAME='${username}'
export MIEMIE_TEST_PASSWORD='${password}'
EOF
  chmod 600 "${BASE_DIR}/env.sh"

  project_status="$(safe_curl -o "${project_body}" -w '%{http_code}' \
    -H "Authorization: Bearer ${TOKEN}" \
    -H 'Content-Type: application/json' \
    -X POST "${LOCAL_BASE}/api/projects" \
    -d "{\"name\":\"W2 Cloudflare Ray 诊断 ${suffix}\",\"description\":\"Cloudflare Ray 慢请求诊断临时项目\"}" || true)"
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

  task_status="$(safe_curl -o "${task_body}" -w '%{http_code}' \
    -H "Authorization: Bearer ${TOKEN}" \
    -H 'Content-Type: application/json' \
    -X POST "${LOCAL_BASE}/api/video-studio" \
    -d "{\"project_id\":\"${PROJECT_ID}\",\"task_type\":\"text_to_video\",\"prompt\":\"W2 Cloudflare Ray 诊断平台侧无key任务\",\"group_count\":1}" || true)"
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
keep = ["id", "project_id", "name", "task_type", "task_kind", "provider", "model_id", "status", "submit_state", "created_at", "updated_at"]
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps({k: data.get(k) for k in keep}, ensure_ascii=False, indent=2))
PY
  rm -f "${task_body}"
  if [ -z "${PROJECT_ID}" ] || [ -z "${TASK_ID}" ]; then
    fail_run "empty project or task id"
    return 1
  fi
  sleep 3
  safe_curl -o "${BASE_DIR}/task-status-snapshot.json" -H "Authorization: Bearer ${TOKEN}" "${LOCAL_BASE}/api/video-studio/${TASK_ID}/status" || true
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
print("\t".join([label, str(vus), duration, f"{failed:.9f}", f"{p95:.6f}", f"{p99:.6f}", str(count), str(checks_fails), "1" if ok else "0", reason]))
PY
}

summarize_samples() {
  local label="$1"
  python3 - "${BASE_DIR}/${label}.log" "${BASE_DIR}/${label}.sample-summary.json" <<'PY'
import collections, json, re, sys
log_path, out_path = sys.argv[1:3]
samples = []
for line in open(log_path, encoding="utf-8", errors="replace"):
    match = re.search(r"(SLOW_SAMPLE|FAIL_SAMPLE) (\{.*\})", line)
    if not match:
        continue
    try:
        samples.append(json.loads(match.group(2)))
    except json.JSONDecodeError:
        continue

def colo(ray):
    if not ray or "-" not in ray:
        return ""
    return ray.rsplit("-", 1)[-1]

by_kind = collections.Counter(item.get("kind", "") for item in samples)
by_colo = collections.Counter(colo(item.get("cf_ray", "")) for item in samples)
by_url = collections.Counter(item.get("url", "") for item in samples)
durations = [item.get("duration_ms") for item in samples if isinstance(item.get("duration_ms"), (int, float))]
out = {
    "sample_count": len(samples),
    "by_kind": dict(by_kind),
    "by_colo": dict(by_colo),
    "by_url": dict(by_url),
    "max_duration_ms": max(durations) if durations else None,
    "top_samples": sorted(samples, key=lambda item: item.get("duration_ms") or 0, reverse=True)[:20],
}
open(out_path, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=2))
PY
}

run_stage() {
  local vus="${K6_VUS:-100}"
  local label="${DIAG_LABEL:-cf-ray-status-${vus}}"
  local duration="${K6_DURATION:-120s}"
  local summary="${BASE_DIR}/${label}.summary.json"
  local log="${BASE_DIR}/${label}.log"
  local gate="${BASE_DIR}/${label}.gate.json"
  local query_urls="/api/projects,/api/video-studio?project_id=${PROJECT_ID},/api/video-studio/${TASK_ID},/api/video-studio/${TASK_ID}/status"
  CURRENT_STAGE="${label}"
  write_status "running" "$CURRENT_STAGE" ""
  log_event "stage ${label} start"
  printf 'label\tvus\tduration\thttp_req_failed\tp95_ms\tp99_ms\thttp_reqs\tchecks_fails\tok\treason\n' > "${RESULTS_FILE}"

  MIEMIE_BASE_URL="${PUBLIC_BASE}" \
  MIEMIE_AUTH_TOKEN="${TOKEN}" \
  LOADTEST_RUN_ID="${RUN_ID}" \
  SCENARIO_NAME="${label}" \
  MIEMIE_QUERY_URLS="${query_urls}" \
  K6_VUS="${vus}" \
  K6_DURATION="${duration}" \
  K6_SLEEP_SECONDS="2" \
  SLOW_SAMPLE_MS="${SLOW_SAMPLE_MS:-800}" \
    k6 run --summary-export "${summary}" "${K6_SCRIPT}" > "${log}" 2>&1
  local rc=$?
  gate_summary "${summary}" "${gate}" "${label}" "${vus}" "${duration}" "${rc}" >> "${RESULTS_FILE}"
  summarize_samples "${label}"
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

capture_logs() {
  CURRENT_STAGE="capture-logs"
  write_status "running" "$CURRENT_STAGE" ""
  docker logs --since "${START_ISO}" miemie-pre-api-1 > "${BASE_DIR}/api-window.raw.log" 2>&1 || true
  awk '/"GET \/api\/(projects|video-studio)/ {print $NF}' "${BASE_DIR}/api-window.raw.log" | sort | uniq -c > "${BASE_DIR}/api-status-code-summary.txt" || true
  grep -E 'Request Failed|request timeout|x509|timeout|SLOW_SAMPLE|FAIL_SAMPLE' "${BASE_DIR}"/*.log > "${BASE_DIR}/k6-sample-summary.log" 2>/dev/null || true
  rm -f "${BASE_DIR}/api-window.raw.log"
}

cleanup() {
  CURRENT_STAGE="cleanup"
  write_status "running" "$CURRENT_STAGE" ""
  {
    echo "# cleanup"
    echo "date=$(date -Is)"
    if [ -n "${TASK_ID}" ]; then
      echo "## delete video task"
      safe_curl -o "${BASE_DIR}/delete-task-response.json" -w '%{http_code}\n' -H "Authorization: Bearer ${TOKEN}" -X DELETE "${LOCAL_BASE}/api/video-studio/${TASK_ID}" || true
    fi
    if [ -n "${PROJECT_ID}" ]; then
      echo "## delete project"
      safe_curl -o "${BASE_DIR}/delete-project-response.json" -w '%{http_code}\n' -H "Authorization: Bearer ${TOKEN}" -X DELETE "${LOCAL_BASE}/api/projects/${PROJECT_ID}" || true
    fi
    if [ -n "${TOKEN}" ]; then
      echo "## logout"
      safe_curl -o "${BASE_DIR}/logout-response.json" -w '%{http_code}\n' -H "Authorization: Bearer ${TOKEN}" -X POST "${LOCAL_BASE}/api/auth/logout" || true
    fi
  } > "${BASE_DIR}/cleanup-summary.txt" 2>&1
  rm -f "${BASE_DIR}/env.sh"
  log_event "cleanup done"
}

postcheck() {
  CURRENT_STAGE="postcheck"
  write_status "running" "$CURRENT_STAGE" ""
  {
    echo "# postcheck"
    echo "date=$(date -Is)"
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
}

main() {
  write_status "running" "init" ""
  log_event "run start"
  precheck || true
  if [ "${FAILED}" -eq 0 ]; then prepare_data || true; fi
  if [ "${FAILED}" -eq 0 ]; then run_stage || true; fi
  capture_logs
  cleanup
  postcheck
  if [ "${FAILED}" -eq 0 ]; then
    write_status "passed" "done" ""
    log_event "run passed"
  else
    write_status "failed" "done" "${FAIL_REASON}"
    log_event "run failed ${FAIL_REASON}"
  fi
}

main "$@"
