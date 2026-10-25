const BASE_URL = 'http://127.0.0.1:8000/api'

// The AI summary (local LLM) and first-run predictions can legitimately take 30-60s+ —
// a short default timeout would misreport them as failures rather than "still working".
const DEFAULT_TIMEOUT_MS = 120_000

async function getJson(path, { timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${BASE_URL}${path}`, { signal: controller.signal })
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      throw new Error(body?.detail || `Request failed (${res.status})`)
    }
    return await res.json()
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('Request timed out')
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

// Admin requests carry the admin email as a plain header — see backend/app/core/security.py
// for why this is intentionally not real authentication.
async function postJson(path, body, { timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
    if (!res.ok) {
      const errBody = await res.json().catch(() => null)
      const detail = Array.isArray(errBody?.detail) ? errBody.detail.map((d) => d.msg).join('; ') : errBody?.detail
      throw new Error(detail || `Request failed (${res.status})`)
    }
    return await res.json()
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('Request timed out')
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

async function adminRequest(method, path, adminEmail, body) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(adminEmail ? { 'X-Admin-Email': adminEmail } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const errBody = await res.json().catch(() => null)
    throw new Error(errBody?.detail || `Request failed (${res.status})`)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  health: () => getJson('/health'),
  modelStatus: () => getJson('/models/status'),
  weather: (region) => getJson(`/weather?region=${region}`),
  summary: () => getJson('/summary'),
  predictNepal: (region, includeNarrative = true) =>
    getJson(`/predict/disaster/nepal?region=${region}&include_narrative=${includeNarrative}`),
  // Either a trailing window ({ daysBack }) or an explicit one ({ start, end }, YYYY-MM-DD).
  collinearity: (region, { daysBack = 730, start, end, resample } = {}) => {
    const params = new URLSearchParams({ region })
    if (start) params.set('start', start)
    if (end) params.set('end', end)
    if (!start && !end) params.set('days_back', daysBack)
    if (resample) params.set('resample', resample)
    return getJson(`/analytics/disaster-collinearity?${params}`)
  },
  simulateInteractive: (scenario) => postJson('/simulate/disaster-interactive', scenario),
  incidents: (region) => getJson(`/feeds/incidents?region=${region}`),
  riverDischarge: () => getJson('/feeds/river-discharge'),
  knowledgeGraph: () => getJson('/knowledge-graph'),

  adminWhoami: (email) => adminRequest('GET', '/admin/whoami', email),
  adminDataSources: (email) => adminRequest('GET', '/admin/data-sources', email),
  adminRetrainModels: (email) => adminRequest('POST', '/admin/models/retrain', email),
  adminListSettings: (email) => adminRequest('GET', '/admin/settings', email),
  adminSetSetting: (email, key, value) =>
    adminRequest('POST', '/admin/settings', email, { key, value }),
  adminDeleteSetting: (email, key) => adminRequest('DELETE', `/admin/settings/${key}`, email),
  adminListKgEdges: (email) => adminRequest('GET', '/admin/knowledge-graph/edges', email),
  adminUpsertKgEdge: (email, edge) =>
    adminRequest('POST', '/admin/knowledge-graph/edges', email, edge),
  adminDeleteKgEdge: (email, id) =>
    adminRequest('DELETE', `/admin/knowledge-graph/edges/${id}`, email),
}
