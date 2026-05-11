import http from 'k6/http'
import { check, fail, sleep } from 'k6'

const baseUrl = (__ENV.MIEMIE_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const authToken = (__ENV.MIEMIE_AUTH_TOKEN || '').trim()
const loadtestRunId = (__ENV.LOADTEST_RUN_ID || 'step00-s3-local')
const scenarioName = (__ENV.SCENARIO_NAME || 'S3-task-observe')
const taskStatusUrls = (__ENV.MIEMIE_TASK_STATUS_URLS || '')
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean)
const submitUrl = (__ENV.MIEMIE_SUBMIT_URL || '').trim()
const submitBody = (__ENV.MIEMIE_SUBMIT_BODY || '').trim()

export const options = {
  vus: Number(__ENV.K6_VUS || 10),
  duration: __ENV.K6_DURATION || '30s',
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<800'],
  },
}

function buildHeaders() {
  const headers = {
    'Content-Type': 'application/json',
    'X-Request-ID': `${loadtestRunId}-${scenarioName}-${__VU}-${__ITER}`,
  }

  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`
  }

  return headers
}

function hasHeader(response, headerName) {
  const expected = headerName.toLowerCase()
  return Object.keys(response.headers || {}).some((key) => key.toLowerCase() === expected)
}

export default function () {
  if (!taskStatusUrls.length && !(submitUrl && submitBody)) {
    fail('必须至少提供 MIEMIE_TASK_STATUS_URLS，或同时提供 MIEMIE_SUBMIT_URL 与 MIEMIE_SUBMIT_BODY')
  }

  const headers = buildHeaders()

  if (submitUrl && submitBody) {
    const submitResponse = http.post(`${baseUrl}${submitUrl}`, submitBody, { headers })
    check(submitResponse, {
      'submit status acceptable': (response) => response.status >= 200 && response.status < 400,
      'submit has request id': (response) => hasHeader(response, 'X-Request-ID'),
      'submit has deployment version': (response) => hasHeader(response, 'X-Deployment-Version'),
    })
  }

  for (const statusUrl of taskStatusUrls) {
    const response = http.get(`${baseUrl}${statusUrl}`, { headers })
    check(response, {
      'status request acceptable': (current) => current.status >= 200 && current.status < 400,
      'status has request id': (current) => hasHeader(current, 'X-Request-ID'),
      'status has deployment version': (current) => hasHeader(current, 'X-Deployment-Version'),
    })
  }

  sleep(Number(__ENV.K6_SLEEP_SECONDS || 1))
}
