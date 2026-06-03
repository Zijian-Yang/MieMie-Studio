import http from 'k6/http'
import { check, fail, sleep } from 'k6'

const baseUrl = (__ENV.MIEMIE_BASE_URL || 'https://pre-studio.miemie.co').replace(/\/$/, '')
const authToken = (__ENV.MIEMIE_AUTH_TOKEN || '').trim()
const loadtestRunId = (__ENV.LOADTEST_RUN_ID || 'w2-client-cloudflare')
const scenarioName = (__ENV.SCENARIO_NAME || 'client-cloudflare-100')
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
