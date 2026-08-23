import { useState } from 'react'
import { api } from '../api'
import StatusPill from './StatusPill'
import TabBar from './TabBar'

const DISASTER_TABS = [
  { id: 'flood', label: 'Flood' },
  { id: 'fire', label: 'Fire' },
  { id: 'earthquake', label: 'Earthquake' },
]

const METRIC_LABELS = {
  rainfall_mm: { label: 'Rainfall (7-day total)', format: (v) => `${v.toFixed(1)}mm` },
  ndvi: { label: 'Vegetation (NDVI)', format: (v) => v.toFixed(3) },
  no2_smoke_proxy: { label: 'Air quality (smoke proxy)', format: (v) => v.toExponential(2) },
}

function formatInr(value) {
  if (value >= 10_000_000) return `₹${(value / 10_000_000).toFixed(2)} crore`
  if (value >= 100_000) return `₹${(value / 100_000).toFixed(2)} lakh`
  return `₹${Math.round(value).toLocaleString('en-IN')}`
}

export default function DisasterSimulationPanel() {
  const [disasterType, setDisasterType] = useState('flood')
  const [severity, setSeverity] = useState(50)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function handleRun() {
    setLoading(true)
    setError(null)
    api
      .simulateDisaster(disasterType, severity)
      .then(setResult)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  function handleTypeChange(type) {
    setDisasterType(type)
    setResult(null)
    setError(null)
  }

  const rec = result?.reconstruction_estimate
  const metricEntries = result ? Object.entries(result.metrics) : []
  const maxCategoryCost = rec
    ? Math.max(...rec.breakdown_by_category.map((c) => c.estimated_cost_inr))
    : 0

  return (
    <div className="card">
      <h2>What if: disaster event</h2>
      <p className="scenario-desc">
        Simulate a disaster and see the projected effect on health, vegetation, and
        wildlife where a real causal link exists, plus a reconstruction-fund estimate
        broken down by infrastructure category and rebuild priority.
      </p>

      <TabBar tabs={DISASTER_TABS} activeId={disasterType} onChange={handleTypeChange} />

      <div className="field">
        <label>
          <span>Severity</span>
          <span>{severity}%</span>
        </label>
        <input
          type="range"
          min={0}
          max={300}
          step={10}
          value={severity}
          onChange={(e) => setSeverity(Number(e.target.value))}
        />
        <div className="slider-scale">
          <span>0% (no change)</span>
          <span>300% (severe)</span>
        </div>
      </div>

      <button className="run-btn" onClick={handleRun} disabled={loading}>
        {loading ? 'Simulating…' : result ? 'Recalculate' : `Simulate ${disasterType}`}
      </button>

      {error && <div className="error" style={{ marginTop: 10 }}>{error}</div>}

      {!result && !loading && !error && (
        <p className="empty-hint">
          {disasterType === 'earthquake'
            ? "Earthquakes aren't weather-driven, so this only estimates reconstruction cost — no environmental risk outcomes."
            : "Queries live environmental data, so it's slower than the intervention scenarios above (up to ~60s)."}
        </p>
      )}

      {result && (
        <div className="scenario-result">
          {metricEntries.map(([key, m]) => {
            const meta = METRIC_LABELS[key]
            if (!meta || m.projected === undefined) return null
            return (
              <div className="metric-compare" key={key}>
                <div>
                  <span className="metric-label">{meta.label}</span>
                  <span className="metric-values">
                    {meta.format(m.current)} <span className="arrow">→</span>{' '}
                    {meta.format(m.projected)}
                  </span>
                </div>
              </div>
            )
          })}

          {result.outcomes.length > 0 && (
            <div className="outcome-list" style={{ marginTop: 4 }}>
              {result.outcomes.map((o) => (
                <div className="outcome-change" key={o.outcome}>
                  <span className="outcome-name">{o.outcome.replace('_', ' ')}</span>
                  {o.risk_before === o.risk_after ? (
                    <span className="no-change">
                      no change <StatusPill level={o.risk_after} />
                    </span>
                  ) : (
                    <span className="changed">
                      <StatusPill level={o.risk_before} />
                      <span className="arrow">→</span>
                      <StatusPill level={o.risk_after} />
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="reconstruction-box">
            <div className="reconstruction-label">Estimated reconstruction fund</div>
            <div className="reconstruction-value">{formatInr(rec.estimated_cost_inr)}</div>
            <div className="caption" style={{ marginBottom: 12 }}>
              for an estimated{' '}
              {Math.round(rec.affected_population_estimate).toLocaleString('en-IN')} affected
              people
            </div>

            <div className="reconstruction-label" style={{ marginTop: 12, marginBottom: 8 }}>
              Rebuild priority (highest public dependence first)
            </div>
            <div className="breakdown-grid">
              {rec.breakdown_by_category.map((c) => (
                <div className="breakdown-card" key={c.category}>
                  <div className="breakdown-card-head">
                    <span className="rank">#{c.priority}</span>
                    <span className="label">{c.label}</span>
                  </div>
                  <div className="amount">{formatInr(c.estimated_cost_inr)}</div>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ width: `${(c.estimated_cost_inr / maxCategoryCost) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <details className="assumption-details">
            <summary>How is this estimated?</summary>
            <p>{result.assumption}</p>
            <p style={{ marginTop: 8 }}>{rec.assumption}</p>
          </details>
        </div>
      )}
    </div>
  )
}
