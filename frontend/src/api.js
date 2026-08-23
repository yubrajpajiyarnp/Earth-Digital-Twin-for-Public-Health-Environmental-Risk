const BASE_URL = 'http://127.0.0.1:8000/api'

// NDVI-backed and RL endpoints can legitimately take 30-90s+ (see CLAUDE.md) — a short
// default timeout would misreport them as failures rather than "still working".
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

// Admin requests carry the admin email as a plain header — see backend/app/core/admin.py
// for why this is intentionally not real authentication.
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
  aqiProxy: () => getJson('/aqi-proxy'),
  forecastAqi: (horizonDays = 7) => getJson(`/forecast/aqi?horizon_days=${horizonDays}`),
  riskAqi: (horizonDays = 7) => getJson(`/risk/aqi?horizon_days=${horizonDays}`),
  explainAqi: () => getJson('/explain/aqi'),
  ndvi: () => getJson('/ndvi'),
  riskVegetation: () => getJson('/risk/vegetation'),
  rainfall: () => getJson('/rainfall'),
  riskFlood: () => getJson('/risk/flood'),
  fauna: () => getJson('/fauna'),
  riskFauna: () => getJson('/risk/fauna'),
  simulateTraffic: (reductionPct) =>
    getJson(`/simulate/traffic-reduction?reduction_pct=${reductionPct}`),
  simulateAfforestation: (areaPct) =>
    getJson(`/simulate/afforestation?area_pct=${areaPct}`),
  simulateDisaster: (disasterType, severityPct) =>
    getJson(`/simulate/disaster?disaster_type=${disasterType}&severity_pct=${severityPct}`),
  optimizeBudget: (budget, fuelPriceInr) =>
    getJson(
      `/optimize/budget?budget=${budget}${fuelPriceInr ? `&fuel_price_inr=${fuelPriceInr}` : ''}`,
    ),
  knowledgeGraph: () => getJson('/knowledge-graph'),

  historyNo2: (limitDays = 365) => getJson(`/history/no2?limit_days=${limitDays}`),
  historyNdvi: (limitDays = 365) => getJson(`/history/ndvi?limit_days=${limitDays}`),
  historyRainfall: (limitDays = 365) => getJson(`/history/rainfall?limit_days=${limitDays}`),
  historyFauna: (limit = 365) => getJson(`/history/fauna?limit=${limit}`),
  forecastAccuracy: (indicator = 'no2') => getJson(`/history/forecast-accuracy?indicator=${indicator}`),

  adminWhoami: (email) => adminRequest('GET', '/admin/whoami', email),
  adminDeleteHistory: (email, indicator, id) =>
    adminRequest('DELETE', `/admin/history/${indicator}/${id}`, email),
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
