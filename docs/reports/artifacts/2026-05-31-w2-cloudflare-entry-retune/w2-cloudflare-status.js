import http from 'k6/http'
import { check, fail, sleep } from 'k6'

const baseUrl = (__ENV.MIEMIE_BASE_URL || 'https://pre-studio.miemie.co').replace(/\/$/, '')
const authToken = (__ENV.MIEMIE_AUTH_TOKEN || '').trim()
const loadtestRunId = (__ENV.LOADTEST_RUN_ID || 'w2-cloudflare-entry')
const scenarioName = (__ENV.SCENARIO_NAME || 'status-observation')
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
    fail('必须提供 MIEMIE_QUERY_URLS')
  }
  for (const queryUrl of queryUrls) {
    const response = http.get(`${baseUrl}${queryUrl}`, { headers: buildHeaders('query') })
    check(response, {
      'query status acceptable': (current) => current.status >= 200 && current.status < 400,
      'query has request id': (current) => hasHeader(current, 'X-Request-ID'),
      'query has deployment version': (current) => hasHeader(current, 'X-Deployment-Version'),
    })
  }
  sleep(Number(__ENV.K6_SLEEP_SECONDS || 2))
}
