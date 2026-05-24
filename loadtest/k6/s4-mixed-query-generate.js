import http from 'k6/http'
import { check, fail, sleep } from 'k6'

const baseUrl = (__ENV.MIEMIE_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const authToken = (__ENV.MIEMIE_AUTH_TOKEN || '').trim()
const loadtestRunId = (__ENV.LOADTEST_RUN_ID || 's4-mixed-local')
const scenarioName = (__ENV.SCENARIO_NAME || 'S4-mixed-query-generate')
const queryUrls = (__ENV.MIEMIE_QUERY_URLS || '')
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean)
const submitUrl = (__ENV.MIEMIE_SUBMIT_URL || '').trim()
const submitBody = (__ENV.MIEMIE_SUBMIT_BODY || '').trim()
const submitEvery = Math.max(0, Number(__ENV.MIEMIE_SUBMIT_EVERY || 0))

export const options = {
  vus: Number(__ENV.K6_VUS || 100),
  duration: __ENV.K6_DURATION || '60s',
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<800'],
  },
}

function buildHeaders(operation) {
  const headers = {
    'Content-Type': 'application/json',
    'X-Request-ID': `${loadtestRunId}-${scenarioName}-${operation}-${__VU}-${__ITER}`,
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
  if (!queryUrls.length) {
    fail('必须提供 MIEMIE_QUERY_URLS，例如 /api/projects,/api/studio?project_id=<project-id>')
  }

  const shouldSubmit = submitUrl && submitBody && submitEvery > 0 && __ITER % submitEvery === 0

  for (const queryUrl of queryUrls) {
    const response = http.get(`${baseUrl}${queryUrl}`, { headers: buildHeaders('query') })
    check(response, {
      'query status acceptable': (current) => current.status >= 200 && current.status < 400,
      'query has request id': (current) => hasHeader(current, 'X-Request-ID'),
      'query has deployment version': (current) => hasHeader(current, 'X-Deployment-Version'),
    })
  }

  if (shouldSubmit) {
    const response = http.post(`${baseUrl}${submitUrl}`, submitBody, { headers: buildHeaders('submit') })
    check(response, {
      'submit status controlled': (current) => current.status >= 200 && current.status < 500,
      'submit has request id': (current) => hasHeader(current, 'X-Request-ID'),
      'submit has deployment version': (current) => hasHeader(current, 'X-Deployment-Version'),
    })
  }

  sleep(Number(__ENV.K6_SLEEP_SECONDS || 2))
}
