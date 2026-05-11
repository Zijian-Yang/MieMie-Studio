import http from 'k6/http'
import { check, sleep } from 'k6'

const baseUrl = (__ENV.MIEMIE_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const authToken = (__ENV.MIEMIE_AUTH_TOKEN || '').trim()
const loadtestRunId = (__ENV.LOADTEST_RUN_ID || 'step00-s1-local')
const scenarioName = (__ENV.SCENARIO_NAME || 'S1-read-baseline')

export const options = {
  vus: Number(__ENV.K6_VUS || 10),
  duration: __ENV.K6_DURATION || '30s',
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<300'],
  },
}

function buildHeaders() {
  const headers = {
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
  const headers = buildHeaders()

  const healthResponse = http.get(`${baseUrl}/api/health`, { headers })
  check(healthResponse, {
    'health status 200': (response) => response.status === 200,
    'health has request id': (response) => hasHeader(response, 'X-Request-ID'),
    'health has deployment version': (response) => hasHeader(response, 'X-Deployment-Version'),
  })

  if (authToken) {
    const modelsResponse = http.get(`${baseUrl}/api/models`, { headers })
    check(modelsResponse, {
      'models status 200': (response) => response.status === 200,
      'models has request id': (response) => hasHeader(response, 'X-Request-ID'),
      'models has deployment version': (response) => hasHeader(response, 'X-Deployment-Version'),
    })

    const projectsResponse = http.get(`${baseUrl}/api/projects`, { headers })
    check(projectsResponse, {
      'projects status 200': (response) => response.status === 200,
      'projects has request id': (response) => hasHeader(response, 'X-Request-ID'),
      'projects has deployment version': (response) => hasHeader(response, 'X-Deployment-Version'),
    })
  }

  sleep(Number(__ENV.K6_SLEEP_SECONDS || 1))
}
