import { useEffect, useState } from 'react'
import { api } from '../api'
import StatTile from './StatTile'
import StatusPill from './StatusPill'
import LineChart from './LineChart'

export default function RainfallPanel() {
  const [rain, setRain] = useState(null)
  const [risk, setRisk] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.rainfall(), api.riskFlood()])
      .then(([r, k]) => {
        setRain(r)
        setRisk(k)
      })
      .catch((err) => setError(err.message))
  }, [])

  if (error) return <div className="card error">Rainfall pipeline failed to load: {error}</div>
  if (!rain || !risk) {
    return (
      <div className="card loading">
        <span className="spinner" />
        Loading rainfall data…
      </div>
    )
  }

  const current = rain.series[rain.series.length - 1]

  return (
    <>
      <div className="grid">
        <StatTile
          label="Rainfall (latest day)"
          value={`${current.value.toFixed(1)} mm`}
          caption={`${current.date} · ${rain.day_count} days of CHIRPS history`}
          accent="var(--series-1)"
        />
        <StatTile
          label={`Last ${risk.recent_window_days}-day total`}
          value={`${risk.recent_total_mm.toFixed(1)} mm`}
          caption={`${risk.pct_change_vs_baseline >= 0 ? '+' : ''}${risk.pct_change_vs_baseline.toFixed(1)}% vs typical ${risk.recent_window_days}-day total`}
          accent="var(--series-1)"
        />
        <div className="card stat-tile" style={{ '--stat-accent': 'var(--status-critical)' }}>
          <div className="label">Flood risk</div>
          <StatusPill level={risk.risk_level} />
        </div>
      </div>

      <div className="card">
        <h2>Daily rainfall</h2>
        <LineChart
          points={rain.series.map((p) => ({ x: p.date, y: p.value }))}
          color="var(--series-1)"
          formatValue={(v) => `${v.toFixed(1)}mm`}
          formatLabel={(d) => d.slice(5)}
        />
        <div className="caption">CHIRPS daily precipitation estimate, ~5.5km resolution.</div>
      </div>

      <div className="card">
        <h2>Outcomes linked to heavy rainfall</h2>
        {risk.outcomes.map((o) => (
          <div className="outcome-row" key={o.outcome}>
            <div style={{ flex: 1 }}>
              <div className="name">{o.outcome.replace('_', ' ')}</div>
              <div className="mechanism">{o.explanation}</div>
              <div className="citation">{o.citation}</div>
            </div>
            <StatusPill level={o.risk_level} />
          </div>
        ))}
      </div>
    </>
  )
}
